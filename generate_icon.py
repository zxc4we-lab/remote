"""
Terminal Icon Generator
Creates a simple terminal icon and saves it as an ICO file.
"""

from PIL import Image, ImageDraw, ImageFont

def create_terminal_icon(output_path, size=256):
    # Create a new image with transparent background
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    
    # Define colors
    bg_color = (42, 42, 42)  # Dark gray
    border_color = (80, 80, 80)  # Lighter gray
    text_color = (0, 255, 0)  # Green
    
    # Calculate padding and sizes
    padding = size // 16
    border_radius = size // 16
    
    # Draw rounded rectangle for terminal background
    rect_bounds = (padding, padding, size - padding, size - padding)
    draw.rounded_rectangle(rect_bounds, fill=bg_color, outline=border_color, width=2, radius=border_radius)
    
    # Draw prompt symbol
    text_size = size // 4
    try:
        # Try to use a font if available
        font = ImageFont.truetype("arial.ttf", text_size)
    except:
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", text_size)
        except:
            font = ImageFont.load_default()
    
    # Draw a cursor and prompt
    prompt_x = size // 4
    prompt_y = size // 2 - text_size // 2
    
    # Draw prompt symbol
    draw.text((prompt_x, prompt_y), ">_", fill=text_color, font=font)
    
    # Save the icon as ICO
    icon.save(output_path, format="ICO", sizes=[(size, size)])
    print(f"Terminal icon created at: {output_path}")

if __name__ == "__main__":
    import os
    
    # Create the icon in the current directory
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terminal_icon.ico")
    create_terminal_icon(output_path)
