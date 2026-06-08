from PIL import Image
from pathlib import Path

def lower_resolution_all():
    utils_dir = Path("assets/")
    for img_path in utils_dir.rglob("*"):
        if img_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            print(f"Resizing {img_path.name}...")
            try:
                img = Image.open(img_path)
                img.thumbnail((64, 64))
                img.save(img_path, img.format)
            except Exception as e:
                print(f"Could not resize {img_path.name}: {e}")
    print("Done!")

if __name__ == "__main__":
    lower_resolution_all()