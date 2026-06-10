import framebuf
from page import Page
import sd

class ScreenModePage(Page):
    """Displays .bmp photos from the SD card."""

    def __init__(self):
        self.title = "Screen Mode"
        self.files = []
        self.current_idx = 0
        self.error_msg = None

    def on_enter(self, app):
        try:
            sd.mount_sd()
            self.files = sd.list_bmp_files()
            if not self.files:
                self.error_msg = "No .bmp files found"
            else:
                self.error_msg = None
                self.current_idx = 0
        except Exception as e:
            self.error_msg = f"SD Error: {e}"

    def handle_input(self, app, diff, clicked, long_press):
        if diff > 0:
            if self.files:
                self.current_idx = (self.current_idx + 1) % len(self.files)
        elif diff < 0:
            if self.files:
                self.current_idx = (self.current_idx - 1) % len(self.files)

        if clicked:
            if self.files:
                self.current_idx = (self.current_idx + 1) % len(self.files)

        return "redraw"

    def _draw_bmp(self, oled, filename):
        path = "/sd/" + filename
        try:
            with open(path, "rb") as f:
                header = f.read(14)
                if header[:2] != b"BM":
                    oled.text("Invalid BMP", 0, 20, 1)
                    return
                offset = int.from_bytes(header[10:14], "little")
                
                dib_header_size_bytes = f.read(4)
                dib_header_size = int.from_bytes(dib_header_size_bytes, "little")
                dib = f.read(36) 
                
                width = int.from_bytes(dib[0:4], "little")
                height_raw = int.from_bytes(dib[4:8], "little")
                if height_raw >= 0x80000000:
                    height_raw -= 0x100000000
                    
                bpp = int.from_bytes(dib[10:12], "little")
                height = abs(height_raw)
                bottom_up = height_raw > 0
                
                print(f"Loading BMP: {filename}, {width}x{height}, {bpp}bpp")
                
                if bpp not in (1, 4, 8, 16, 24, 32):
                    oled.text(f"Bad BPP: {bpp}", 0, 20, 1)
                    return
                
                palette = None
                if bpp in (1, 4, 8):
                    colors = int.from_bytes(dib[28:32], "little")
                    if colors == 0:
                        colors = 1 << bpp
                    f.seek(14 + dib_header_size)
                    palette = f.read(colors * 4)
                
                buf = bytearray(128 * 64 // 8)
                f.seek(offset)
                row_size = ((width * bpp + 31) // 32) * 4
                
                # Scale to fit in 128x48 (the blue zone)
                scale_x = 128 / width
                scale_y = 48 / height
                scale = min(scale_x, scale_y)
                if scale > 1.0:
                    scale = 1.0
                    
                new_w = int(width * scale)
                new_h = int(height * scale)
                x_offset = (128 - new_w) // 2
                y_offset = (48 - new_h) // 2 + 16 # Start at y=16 (blue zone)
                
                BAYER = [
                    [  0, 136,  34, 170],
                    [204,  68, 238, 102],
                    [ 51, 187,  17, 153],
                    [255, 119, 221,  85]
                ]
                
                last_target_y = -1
                for y_file in range(height):
                    y_orig = (height - 1 - y_file) if bottom_up else y_file
                    target_y = int(y_orig * scale)
                    
                    if target_y >= new_h:
                        target_y = new_h - 1
                        
                    # Decimate rows if shrinking to save CPU
                    if target_y == last_target_y and scale < 1.0:
                        f.read(row_size)
                        continue
                        
                    last_target_y = target_y
                    row_data = f.read(row_size)
                    
                    screen_y = target_y + y_offset
                    if screen_y < 16 or screen_y >= 64:
                        continue
                        
                    bayer_row = BAYER[screen_y % 4]
                    
                    for target_x in range(new_w):
                        x_orig = int(target_x / scale)
                        if x_orig >= width: x_orig = width - 1
                        
                        screen_x = target_x + x_offset
                        if screen_x < 0 or screen_x >= 128:
                            continue
                            
                        # Extract pixel
                        r = g = b = 0
                        if bpp == 1:
                            bit = (row_data[x_orig // 8] >> (7 - (x_orig % 8))) & 1
                            r = g = b = 255 if bit else 0
                        elif bpp == 4:
                            idx = (row_data[x_orig // 2] >> (4 if x_orig % 2 == 0 else 0)) & 0x0F
                            b, g, r = palette[idx*4], palette[idx*4+1], palette[idx*4+2]
                        elif bpp == 8:
                            idx = row_data[x_orig]
                            b, g, r = palette[idx*4], palette[idx*4+1], palette[idx*4+2]
                        elif bpp == 16:
                            px = row_data[x_orig*2] | (row_data[x_orig*2+1] << 8)
                            r = ((px >> 11) & 0x1F) * 255 // 31
                            g = ((px >> 5) & 0x3F) * 255 // 63
                            b = (px & 0x1F) * 255 // 31
                        elif bpp == 24:
                            b, g, r = row_data[x_orig*3], row_data[x_orig*3+1], row_data[x_orig*3+2]
                        elif bpp == 32:
                            b, g, r = row_data[x_orig*4], row_data[x_orig*4+1], row_data[x_orig*4+2]
                            
                        # Dither
                        brightness = (r + g + b) // 3
                        if brightness > bayer_row[screen_x % 4]:
                            buf[screen_y * 16 + (screen_x // 8)] |= (1 << (7 - (screen_x % 8)))
                
                fbuf = framebuf.FrameBuffer(buf, 128, 64, framebuf.MONO_HMSB)
                oled.fill(0)
                # Draw a subtle header in the yellow zone
                oled.text(filename[:16], 0, 4, 1)
                oled.hline(0, 14, 128, 1)
                oled.blit(fbuf, 0, 0)
                
        except Exception as e:
            oled.text("Parse Error", 0, 20, 1)
            print("BMP parse error:", e)

    def draw(self, oled):
        if self.error_msg:
            oled.fill(0)
            oled.text(self.title, 0, 4, 1)
            oled.hline(0, 14, 128, 1)
            oled.text(self.error_msg[:16], 0, 25, 1)
        elif not self.files:
            oled.fill(0)
            oled.text(self.title, 0, 4, 1)
            oled.hline(0, 14, 128, 1)
            oled.text("No .bmp found", 0, 25, 1)
        else:
            self._draw_bmp(oled, self.files[self.current_idx])
