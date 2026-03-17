import torch
import numpy as np
import cv2

class PollyEmissiveColor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (["Vivid (Lava/Neon)", "Brightest Pixel", "Dominant (Average)", "Manual Override"], 
                         {"default": "Vivid (Lava/Neon)"}),
                "blur_amount": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "mask_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "saturation_filter": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.05}),
                "color_boost": ("FLOAT", {"default": 3.0, "min": 1.0, "max": 10.0, "step": 0.1}),
                "color_picker_override": ("STRING", {"default": "#FF6600"}), # Changed from COLOR to STRING
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE", "IMAGE")
    RETURN_NAMES = ("Mask", "Emissive", "Solid Color")
    FUNCTION = "process"
    CATEGORY = "Polly Creative > textures"

    def hex_to_rgb(self, hex_color):
        try:
            hex_str = str(hex_color).lstrip('#')
            return np.array([int(hex_str[i:i+2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0
        except Exception:
            return np.array([1.0, 1.0, 1.0], dtype=np.float32)

    def process(self, image, mode, blur_amount, mask_threshold, saturation_filter, color_boost, color_picker_override):
        batch_size, height, width, _ = image.shape
        out_masks, out_emissive, out_solid = [], [], []

        manual_rgb = self.hex_to_rgb(color_picker_override)

        for i in range(batch_size):
            img_rgb = image[i].cpu().numpy().astype(np.float32)
            
            # 1. Advanced Masking
            img_uint8 = (img_rgb * 255).clip(0, 255).astype(np.uint8)
            hsv_full = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
            
            sat_map = hsv_full[..., 1] / 255.0
            val_map = hsv_full[..., 2] / 255.0
            
            combined_map = val_map * (sat_map + (1.0 - saturation_filter))
            c_max = combined_map.max()
            if c_max > 0:
                combined_map /= c_max
            
            mask_np = (combined_map >= mask_threshold).astype(np.float32)
            
            if blur_amount > 0:
                ksize = int(blur_amount * 2) // 2 * 2 + 1
                mask_np = cv2.GaussianBlur(mask_np, (ksize, ksize), blur_amount)

            # 2. Color Selection
            if mode == "Manual Override":
                final_color = manual_rgb
            else:
                sample_indices = val_map > 0.1
                if np.any(sample_indices):
                    pixels = img_rgb[sample_indices]
                    pix_hsv = hsv_full[sample_indices]
                    
                    if mode == "Vivid (Lava/Neon)":
                        sats = pix_hsv[:, 1] / 255.0
                        vals = pix_hsv[:, 2] / 255.0
                        scores = vals * (sats ** color_boost)
                        final_color = pixels[np.argmax(scores)]
                    elif mode == "Brightest Pixel":
                        lum = (pixels[:, 0] * 0.299 + pixels[:, 1] * 0.587 + pixels[:, 2] * 0.114)
                        final_color = pixels[np.argmax(lum)]
                    else:
                        final_color = pixels.mean(axis=0)
                else:
                    final_color = np.array([0.0, 0.0, 0.0], dtype=np.float32)

            # 3. Build Tensors
            emissive_rgb = np.expand_dims(mask_np, axis=-1) * final_color
            solid_rgb = np.ones((height, width, 3), dtype=np.float32) * final_color

            out_masks.append(torch.from_numpy(mask_np))
            out_emissive.append(torch.from_numpy(emissive_rgb))
            out_solid.append(torch.from_numpy(solid_rgb))

        return (
            torch.stack(out_masks, dim=0), 
            torch.stack(out_emissive, dim=0), 
            torch.stack(out_solid, dim=0)
        )

NODE_CLASS_MAPPINGS = {
    "PollyEmissiveColor": PollyEmissiveColor
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PollyEmissiveColor": "Emissive Color (Polly)"
}