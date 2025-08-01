from flask import Flask, render_template, request, redirect, send_from_directory, url_for
import os
import subprocess
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError, ImageOps
import time
import mimetypes

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
THUMB_FOLDER = 'static/uploads/thumbs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMB_FOLDER'] = THUMB_FOLDER

# Recognize common video types
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/quicktime", ".mov")
mimetypes.add_type("video/x-msvideo", ".avi")

def get_file_type(filename):
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith('image/'):
        return 'image'
    elif mime_type and mime_type.startswith('video/'):
        return 'video'
    return 'other'

# Generate video thumbnail using ffmpeg
def generate_video_thumbnail(video_path, thumb_path):
    try:
        thumb_path = os.path.splitext(thumb_path)[0] + ".jpg"
        subprocess.run([
            'ffmpeg', '-y',
            '-ss', '00:00:01',
            '-i', video_path,
            '-vframes', '1',
            '-vf', 'scale=400:-1',
            thumb_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[✓] Generated video thumbnail for: {os.path.basename(video_path)}")
        return True
    except Exception as e:
        print(f"[✗] Error generating video thumbnail for {os.path.basename(video_path)}: {e}")
        return False

def generate_missing_thumbnails():
    print("Generating missing thumbnails...")
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename == 'thumbs':
            continue
        
        full_path = os.path.join(UPLOAD_FOLDER, filename)
        ext = os.path.splitext(filename)[1]
        thumb_base = os.path.splitext(filename)[0]
        file_type = get_file_type(filename)

        if file_type == 'video':
            thumb_path = os.path.join(THUMB_FOLDER, thumb_base + ".jpg")
        else:
            thumb_path = os.path.join(THUMB_FOLDER, filename)

        if not os.path.isfile(full_path):
            continue

        regenerate_thumb = True
        if os.path.exists(thumb_path):
            if os.path.getmtime(thumb_path) >= os.path.getmtime(full_path):
                regenerate_thumb = False

        if regenerate_thumb:
            if file_type == 'image':
                try:
                    img = Image.open(full_path)
                    img = ImageOps.exif_transpose(img)
                    if img.mode in ('RGBA', 'P', 'CMYK'):
                        img = img.convert('RGB')
                    img.thumbnail((400, 300))
                    img.save(thumb_path)
                    print(f"[✓] Generated image thumbnail for: {filename}")
                except UnidentifiedImageError:
                    print(f"[✗] Skipped (PIL could not identify image): {filename}")
                except Exception as e:
                    print(f"[✗] Error generating image thumbnail for {filename}: {e}")
            elif file_type == 'video':
                generate_video_thumbnail(full_path, thumb_path)
            else:
                print(f"[✗] Skipped (unsupported file type): {filename}")

generate_missing_thumbnails()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        for file_storage in request.files.getlist('images'):
            if file_storage.filename:
                filename = secure_filename(file_storage.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    print(f"File '{filename}' already exists. Skipping upload.")
                    continue

                file_storage.save(filepath)
                file_type = get_file_type(filename)
                thumb_base = os.path.splitext(filename)[0]
                if file_type == 'image':
                    try:
                        img = Image.open(filepath)
                        img = ImageOps.exif_transpose(img)
                        if img.mode in ('RGBA', 'P', 'CMYK'):
                            img = img.convert('RGB')
                        img.thumbnail((400, 300))
                        thumb_path = os.path.join(THUMB_FOLDER, filename)
                        img.save(thumb_path)
                        print(f"[✓] Image thumbnail generated for new upload: {filename}")
                    except Exception as e:
                        print(f"[✗] Error processing image {filename}: {e}")
                elif file_type == 'video':
                    thumb_path = os.path.join(THUMB_FOLDER, thumb_base + ".jpg")
                    generate_video_thumbnail(filepath, thumb_path)
                else:
                    print(f"Unsupported type for: {filename}")
        return redirect(url_for('index'))

    media_items = []
    for media_name in os.listdir(UPLOAD_FOLDER):
        if media_name == 'thumbs':
            continue

        full_path = os.path.join(UPLOAD_FOLDER, media_name)
        if not os.path.isfile(full_path):
            continue

        file_type = get_file_type(media_name)
        thumb_base = os.path.splitext(media_name)[0]
        thumb_name = media_name if file_type == 'image' else thumb_base + ".jpg"
        thumb_path = os.path.join(THUMB_FOLDER, thumb_name)
        has_thumb = os.path.exists(thumb_path)
        cache_buster = int(os.path.getmtime(thumb_path) if has_thumb else os.path.getmtime(full_path))

        media_items.append({
            'name': media_name,
            'type': file_type,
            'thumb': thumb_name,
            'cache_buster': cache_buster
        })

    return render_template('index.html', media_items=media_items)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(app.config['THUMB_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)