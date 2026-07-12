import os
import json
import time
import re
import sys
import socket
import asyncio
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import webbrowser
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max limit

# Path to ADB binary
ADB_PATH = '/opt/homebrew/bin/adb'
if not os.path.exists(ADB_PATH):
    ADB_PATH = 'adb'  # Fallback to PATH

def run_adb(args, timeout=15):
    """Run an ADB command and return stdout, stderr, and return code."""
    cmd = [ADB_PATH] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -2

def get_local_subnet():
    """Get the local subnet prefix (e.g., '10.0.0.')."""
    try:
        # Create a dummy socket to find active interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:3]) + '.'
    except Exception:
        pass
    return '192.168.1.'  # Default fallback

async def check_ip(ip, port=5555, timeout=0.3):
    """Check if port 5555 is open on a given IP."""
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return ip
    except Exception:
        return None

async def scan_network(subnet_prefix):
    """Scan subnet IPs on port 5555 in parallel."""
    tasks = []
    for i in range(1, 255):
        ip = f"{subnet_prefix}{i}"
        tasks.append(check_ip(ip))
    results = await asyncio.gather(*tasks)
    return [ip for ip in results if ip is not None]

def get_connected_devices():
    """Get list of connected ADB devices and their states."""
    stdout, _, _ = run_adb(['devices'])
    devices = []
    lines = stdout.split('\n')[1:]  # Skip header
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append({
                'id': parts[0],
                'state': parts[1]  # 'device', 'unauthorized', 'offline'
            })
    return devices

def parse_bounds(bounds_str):
    """Parse UI Automator bounds string '[x1,y1][x2,y2]' to center (x, y)."""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def find_node_by_criteria(root, criteria_fn):
    """Recursively find a node matching criteria function."""
    if criteria_fn(root):
        return root
    for child in root:
        found = find_node_by_criteria(child, criteria_fn)
        if found is not None:
            return found
    return None

def get_adb_target(ip):
    """Determine the correct target identifier for ADB."""
    if not ip:
        return ""
    # If it is a USB serial (alphanumeric, no dots/colons)
    if '.' not in ip and ':' not in ip:
        return ip
    # If it is an IP address without port, append default 5555
    if ':' not in ip:
        return f"{ip}:5555"
    return ip

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def status():
    devices = get_connected_devices()
    return jsonify({
        'devices': devices,
        'local_subnet': get_local_subnet()
    })

@app.route('/api/scan', methods=['GET'])
def scan():
    subnet = get_local_subnet()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    found_ips = loop.run_until_complete(scan_network(subnet))
    loop.close()
    return jsonify({'found_ips': found_ips})

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json or {}
    ip = data.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP address is required'}), 400
    
    target = get_adb_target(ip)
    is_usb_serial = '.' not in ip and ':' not in ip
    
    if is_usb_serial:
        # Check if the USB device is connected and authorized
        devices = get_connected_devices()
        dev = next((d for d in devices if d['id'] == target), None)
        if dev:
            return jsonify({
                'success': True,
                'message': f'USB device {target} is ready.',
                'device_state': dev['state']
            })
        else:
            return jsonify({
                'success': False,
                'error': f'USB device {target} not found. Check physical connection.'
            })

    # Disconnect first to refresh state
    run_adb(['disconnect', target])
    stdout, stderr, code = run_adb(['connect', target])
    
    if "connected to" in stdout.lower():
        # Check authorization state
        devices = get_connected_devices()
        device_state = 'unknown'
        for d in devices:
            if d['id'] == target or d['id'].startswith(ip):
                device_state = d['state']
                break
        
        return jsonify({
            'success': True,
            'message': stdout,
            'device_state': device_state
        })
    else:
        return jsonify({
            'success': False,
            'error': stdout or stderr or 'Failed to connect'
        })

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    data = request.json or {}
    ip = data.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP address is required'}), 400
    
    is_usb_serial = '.' not in ip and ':' not in ip
    if is_usb_serial:
        return jsonify({'success': True, 'message': 'USB device can only be disconnected by physically unplugging it.'})
        
    target = get_adb_target(ip)
    stdout, stderr, _ = run_adb(['disconnect', target])
    return jsonify({'success': True, 'message': stdout or stderr})

@app.route('/api/setup-wireless', methods=['POST'])
def setup_wireless():
    # Helper to enable wireless debugging over USB
    # Requires device to be plugged in via USB
    stdout, stderr, code = run_adb(['tcpip', '5555'])
    if code == 0:
        return jsonify({'success': True, 'message': 'Wireless debugging port 5555 opened! You can now unplug the USB and connect via Wi-Fi.'})
    else:
        return jsonify({'success': False, 'error': stderr or stdout or 'No USB device detected or command failed.'})

@app.route('/api/send', methods=['POST'])
def send_photos():
    ip = request.form.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP address is required'}), 400
    
    target = get_adb_target(ip)
    
    # Verify device is connected
    devices = get_connected_devices()
    device = None
    for d in devices:
        if d['id'] == target or d['id'].startswith(ip):
            device = d
            break
            
    if not device:
        return jsonify({'success': False, 'error': 'Device is not connected. Connect first.'}), 400
    if device['state'] == 'unauthorized':
        return jsonify({'success': False, 'error': 'Device is unauthorized. Please allow USB debugging on the frame screen.'}), 400

    uploaded_files = request.files.getlist('files')
    if not uploaded_files or len(uploaded_files) == 0:
        return jsonify({'success': False, 'error': 'No files selected.'}), 400

    # Image optimization parameters
    optimize = request.form.get('optimize') == 'true'
    target_width = int(request.form.get('width', 1280))
    target_height = int(request.form.get('height', 800))
    fit_mode = request.form.get('fit_mode', 'cover')  # 'cover' or 'contain'

    results = []
    success_count = 0

    for file in uploaded_files:
        if not file.filename:
            continue
            
        # Secure filename and write to temp directory
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(temp_path)
        
        # Optimize image if requested and is an image file
        is_image = file.content_type.startswith('image/') or file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        if optimize and is_image:
            try:
                from PIL import Image, ImageOps
                with Image.open(temp_path) as img:
                    # Convert to RGB if needed (e.g. PNG/WebP with alpha/transparency)
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        img = img.convert('RGB')
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    if fit_mode == 'cover':
                        resized = ImageOps.fit(img, (target_width, target_height), Image.Resampling.LANCZOS)
                    else:
                        # Contain mode: scale to fit bounds preserving aspect ratio
                        img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                        resized = img
                        
                    resized.save(temp_path, format='JPEG', quality=85)
            except Exception as e:
                print(f"Failed to optimize image {file.filename}, falling back to original: {e}")

        # Target destination on frame
        remote_path = f"/sdcard/DCIM/{file.filename}"
        
        # ADB Push command
        stdout, stderr, code = run_adb(['-s', target, 'push', temp_path, remote_path])
        
        # Clean up local temp file
        try:
            os.remove(temp_path)
        except Exception:
            pass

        if code == 0:
            success_count += 1
            results.append({'file': file.filename, 'status': 'success'})
        else:
            results.append({'file': file.filename, 'status': 'failed', 'error': stderr or stdout})

    # Trigger Media Scan so Frameo system detects new photos
    scan_stdout, scan_stderr, scan_code = run_adb([
        '-s', target, 'shell', 'content', 'call',
        '--method', 'scan_volume',
        '--uri', 'content://media',
        '--arg', 'external_primary'
    ])
    
    # Fallback to secondary broadcast scan if primary failed
    if scan_code != 0:
        run_adb([
            '-s', target, 'shell', 'am', 'broadcast',
            '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE',
            '-d', 'file:///sdcard/DCIM/'
        ])

    return jsonify({
        'success': success_count > 0,
        'success_count': success_count,
        'total_count': len(uploaded_files),
        'results': results,
        'media_scan': {
            'success': scan_code == 0,
            'message': scan_stdout or scan_stderr
        }
    })

@app.route('/api/automate-import', methods=['POST'])
def automate_import():
    data = request.json or {}
    ip = data.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP address is required'}), 400
    
    target = get_adb_target(ip)
    logs = []
    
    def log(msg):
        logs.append(msg)
        print(f"[Automation] {msg}")

    try:
        # 1. Wake screen & Unlock
        log("Waking up device screen...")
        run_adb(['-s', target, 'shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'])
        run_adb(['-s', target, 'shell', 'wm', 'dismiss-keyguard'])
        
        # 2. Reset Frameo app to start from a clean state (slideshow screen)
        log("Resetting Frameo app to slideshow screen...")
        run_adb(['-s', target, 'shell', 'am', 'force-stop', 'net.frameo.frame'])
        time.sleep(0.5)
        log("Launching Frameo app...")
        run_adb(['-s', target, 'shell', 'monkey', '-p', 'net.frameo.frame', '-c', 'android.intent.category.LAUNCHER', '1'])
        await_time = 3.0
        log(f"Waiting {await_time}s for app to load...")
        time.sleep(await_time)

        # Helper to dump and parse layout XML
        def dump_and_parse():
            temp_xml = os.path.join(app.config['UPLOAD_FOLDER'], f"dump_{int(time.time())}.xml")
            # Dump UI XML to device
            _, _, code = run_adb(['-s', target, 'shell', 'uiautomator', 'dump', '/sdcard/window_dump.xml'])
            if code != 0:
                log("Failed to run uiautomator dump on device.")
                return None
            
            # Pull XML
            _, _, code = run_adb(['-s', target, 'pull', '/sdcard/window_dump.xml', temp_xml])
            if code != 0:
                log("Failed to pull window dump from device.")
                return None

            try:
                tree = ET.parse(temp_xml)
                os.remove(temp_xml)
                return tree.getroot()
            except Exception as e:
                log(f"Failed to parse XML dump: {e}")
                if os.path.exists(temp_xml):
                    os.remove(temp_xml)
                return None

        # Step 3. Click Settings (Gear icon)
        log("Looking for Settings button...")
        root = dump_and_parse()
        if root is None:
            return jsonify({'success': False, 'error': 'Failed to read UI structure from screen.', 'logs': logs})

        # Try to find node with resource-id, content-desc or text matching Settings/gear
        def is_settings_node(node):
            res_id = node.get('resource-id', '').lower()
            desc = node.get('content-desc', '').lower()
            text = node.get('text', '').lower()
            return 'settings' in res_id or 'settings' in desc or 'settings' in text or 'action_settings' in res_id

        settings_node = find_node_by_criteria(root, is_settings_node)
        if not settings_node:
            log("Settings button not found by ID/Text. Searching for clickable buttons near corners...")
            # Frameo settings button is usually a gear icon in the top right or side panel.
            # We will fallback to looking for clickable ImageViews/Buttons.
            def is_clickable_icon(node):
                return node.get('clickable') == 'true' and ('image' in node.get('class', '').lower() or 'button' in node.get('class', '').lower())
            
            # Find all clickable buttons
            clickables = []
            def find_clickables(node):
                if is_clickable_icon(node):
                    clickables.append(node)
                for child in node:
                    find_clickables(child)
            find_clickables(root)
            log(f"Found {len(clickables)} clickable icons/buttons.")
            
            # Frameo Settings button is usually at the bottom-right or top-right or center gear.
            # Without specific info, we tell the user.
            log("Automatic Settings gear click failed. Please open Settings manually on the frame, then retry.")
            return jsonify({
                'success': False,
                'error': 'Could not reliably locate Settings button. Please navigate to: Settings -> Manage photos -> Import photos on the frame screen.',
                'logs': logs
            })

        bounds = settings_node.get('bounds')
        coords = parse_bounds(bounds)
        if coords:
            log(f"Clicking Settings gear at {coords}...")
            run_adb(['-s', target, 'shell', 'input', 'tap', str(coords[0]), str(coords[1])])
            time.sleep(1.5)
        else:
            log("Could not parse bounds for Settings node.")
            return jsonify({'success': False, 'error': 'Failed to parse Settings button coordinates.', 'logs': logs})

        # Step 4. Click "Manage photos"
        log("Looking for 'Manage photos' menu item...")
        root = dump_and_parse()
        if root is None:
            return jsonify({'success': False, 'error': 'Failed to read UI structure after clicking Settings.', 'logs': logs})

        def is_manage_photos(node):
            text = node.get('text', '').lower()
            desc = node.get('content-desc', '').lower()
            return 'manage photos' in text or 'manage photos' in desc or 'manage_photos' in node.get('resource-id', '').lower()

        manage_node = find_node_by_criteria(root, is_manage_photos)
        if not manage_node:
            log("'Manage photos' option not found on screen. Check if Settings screen opened successfully.")
            return jsonify({'success': False, 'error': "Could not find 'Manage photos' menu. Please navigate manually.", 'logs': logs})

        coords = parse_bounds(manage_node.get('bounds'))
        if coords:
            log(f"Clicking 'Manage photos' at {coords}...")
            run_adb(['-s', target, 'shell', 'input', 'tap', str(coords[0]), str(coords[1])])
            time.sleep(1.5)
        else:
            return jsonify({'success': False, 'error': "Failed to click 'Manage photos'.", 'logs': logs})

        # Step 5. Click "Import photos"
        log("Looking for 'Import photos' option...")
        root = dump_and_parse()
        if root is None:
            return jsonify({'success': False, 'error': 'Failed to read UI structure after clicking Manage photos.', 'logs': logs})

        def is_import_photos(node):
            text = node.get('text', '').lower()
            desc = node.get('content-desc', '').lower()
            return 'import photos' in text or 'import photos' in desc or 'import_photos' in node.get('resource-id', '').lower()

        import_node = find_node_by_criteria(root, is_import_photos)
        if not import_node:
            log("'Import photos' option not found. Checking if menu was already visible.")
            return jsonify({'success': False, 'error': "Could not find 'Import photos' option.", 'logs': logs})

        coords = parse_bounds(import_node.get('bounds'))
        if coords:
            log(f"Clicking 'Import photos' at {coords}...")
            run_adb(['-s', target, 'shell', 'input', 'tap', str(coords[0]), str(coords[1])])
            time.sleep(2.5)  # Wait longer for media scan/preview grid to load
        else:
            return jsonify({'success': False, 'error': "Failed to click 'Import photos'.", 'logs': logs})

        # Step 6. Select Photos and Import
        log("Looking for photos to select in the Import grid...")
        root = dump_and_parse()
        if root is None:
            return jsonify({'success': False, 'error': 'Failed to read UI structure on Import screen.', 'logs': logs})

        # Look for "Select all" button
        def is_select_all(node):
            text = node.get('text', '').lower()
            desc = node.get('content-desc', '').lower()
            res_id = node.get('resource-id', '').lower()
            return 'select all' in text or 'select all' in desc or 'select_all' in res_id or 'menu_select_all' in res_id

        select_all_node = find_node_by_criteria(root, is_select_all)
        if select_all_node:
            coords = parse_bounds(select_all_node.get('bounds'))
            log(f"Clicking 'Select all' button at {coords}...")
            run_adb(['-s', target, 'shell', 'input', 'tap', str(coords[0]), str(coords[1])])
            time.sleep(1.0)
        else:
            log("'Select all' option not found by text. Attempting to click individual item checkboxes or top bar icons...")
            # Fallback: Just click the top-right button which is usually "Select all" or "Import"
            # Let's search for the actual import button
            
        # Look for the final import confirmation button (often a downward arrow icon or text containing "Import")
        def is_import_button(node):
            text = node.get('text', '').lower()
            desc = node.get('content-desc', '').lower()
            res_id = node.get('resource-id', '').lower()
            # The final import button on the top right
            return 'import' in text or 'import' in desc or 'import' in res_id or 'action_import' in res_id or 'menu_import' in res_id

        import_btn_node = find_node_by_criteria(root, is_import_button)
        if import_btn_node:
            coords = parse_bounds(import_btn_node.get('bounds'))
            log(f"Clicking final Import button at {coords}...")
            run_adb(['-s', target, 'shell', 'input', 'tap', str(coords[0]), str(coords[1])])
            log("Import command triggered successfully!")
            return jsonify({'success': True, 'message': 'Successfully automated photo import sequence!', 'logs': logs})
        else:
            log("Could not find the final Import button. The photos might be selected, but you will need to tap the import arrow (downward arrow in top-right) on the frame screen.")
            return jsonify({
                'success': True,
                'message': 'Photos sent and import screen opened. Please tap the Import button (downward arrow) on the frame to finish.',
                'logs': logs
            })

    except Exception as e:
        log(f"Automation error: {str(e)}")
        return jsonify({'success': False, 'error': f"Automation failed: {str(e)}", 'logs': logs})

def select_folder_native():
    """Spawn a subprocess to run tkinter and open a native folder picker."""
    script = """
import tkinter as tk
from tkinter import filedialog
import os
root = tk.Tk()
root.withdraw()
root.focus_force()
# Try to bring the dialog to the front on macOS
os.system('''/usr/bin/osascript -e 'tell app "System Events" to set frontmost of every process whose unix id is ''' + str(os.getpid()) + ''' to true' &''')
path = filedialog.askdirectory(title='Select Folder to Sync')
print(path)
"""
    try:
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except Exception as e:
        print(f"Failed to run native folder picker: {e}")
        return ""

@app.route('/api/browse-folder', methods=['POST'])
def browse_folder():
    path = select_folder_native()
    return jsonify({'success': bool(path), 'path': path})

@app.route('/api/sync-stream')
def sync_stream():
    folder_path = request.args.get('path')
    ip = request.args.get('ip')
    optimize = request.args.get('optimize') == 'true'
    target_width = int(request.args.get('width', 1280))
    target_height = int(request.args.get('height', 800))
    fit_mode = request.args.get('fit_mode', 'cover')

    def generate():
        if not folder_path or not os.path.isdir(folder_path):
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid folder path'})}\n\n"
            return

        if not ip:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Device IP/Serial is required'})}\n\n"
            return

        target = get_adb_target(ip)
        
        # Verify connection
        devices = get_connected_devices()
        dev = next((d for d in devices if d['id'] == target or d['id'].startswith(ip)), None)
        if not dev:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Device {ip} is not connected'})}\n\n"
            return
        if dev['state'] == 'unauthorized':
            yield f"data: {json.dumps({'type': 'error', 'message': 'Device is unauthorized. Please trust computer on screen.'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'message': 'Scanning folder recursively...'})}\n\n"
        
        # Find all files recursively
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.mp4')
        all_files = []
        for root_dir, _, filenames in os.walk(folder_path):
            for f in filenames:
                if f.lower().endswith(valid_exts):
                    all_files.append(os.path.join(root_dir, f))
        
        total_files = len(all_files)
        yield f"data: {json.dumps({'type': 'status', 'message': f'Found {total_files} files.'})}\n\n"
        
        if total_files == 0:
            yield f"data: {json.dumps({'type': 'complete', 'message': 'No media files found to sync.'})}\n\n"
            return

        # Fetch remote files to check sizes for lazy skipping
        yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching device inventory...'})}\n\n"
        stdout, _, _ = run_adb(['-s', target, 'shell', 'ls', '-la', '/sdcard/DCIM/'])
        
        # Parse device files and sizes
        device_inventory = {}
        for line in stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 8:
                filename = parts[-1]
                try:
                    size = int(parts[4])
                    device_inventory[filename] = size
                except ValueError:
                    pass

        success_count = 0
        skipped_count = 0
        
        for idx, local_path in enumerate(all_files):
            filename = os.path.basename(local_path)
            
            # Send progress event
            yield f"data: {json.dumps({
                'type': 'progress',
                'current': idx + 1,
                'total': total_files,
                'file': filename,
                'status': f'Processing {idx+1}/{total_files}...'
            })}\n\n"
            
            # Prepare temp path
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"sync_{filename}")
            
            is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
            
            # Optimization logic
            pushed_file_path = local_path
            if optimize and is_image:
                try:
                    from PIL import Image, ImageOps
                    with Image.open(local_path) as img:
                        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                            img = img.convert('RGB')
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                            
                        if fit_mode == 'cover':
                            resized = ImageOps.fit(img, (target_width, target_height), Image.Resampling.LANCZOS)
                        else:
                            img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                            resized = img
                        
                        resized.save(temp_path, format='JPEG', quality=85)
                        pushed_file_path = temp_path
                except Exception as e:
                    print(f"Optimization failed for {filename}: {e}")
            
            # Check size for lazy skipping
            try:
                local_size = os.path.getsize(pushed_file_path)
            except OSError:
                local_size = -1
                
            remote_size = device_inventory.get(filename, -2)
            
            if local_size == remote_size:
                skipped_count += 1
                # Clean up temp file
                if pushed_file_path == temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                continue
                
            # Push file
            remote_path = f"/sdcard/DCIM/{filename}"
            _, _, code = run_adb(['-s', target, 'push', pushed_file_path, remote_path])
            
            # Clean up temp file
            if pushed_file_path == temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                
            if code == 0:
                success_count += 1
            else:
                yield f"data: {json.dumps({
                    'type': 'log', 
                    'message': f'Failed to push {filename}',
                    'level': 'error'
                })}\n\n"
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Triggering media scan...'})}\n\n"
        run_adb([
            '-s', target, 'shell', 'content', 'call',
            '--method', 'scan_volume',
            '--uri', 'content://media',
            '--arg', 'external_primary'
        ])
        
        yield f"data: {json.dumps({
            'type': 'complete',
            'message': f'Sync finished! Transferred: {success_count}, Skipped: {skipped_count}, Total: {total_files}'
        })}\n\n"
        
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/device/storage', methods=['GET'])
def device_storage():
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP/Serial is required'}), 400
    target = get_adb_target(ip)
    stdout, stderr, code = run_adb(['-s', target, 'shell', 'df', '/sdcard'])
    if code != 0:
        return jsonify({'success': False, 'error': f'Failed to run df: {stderr or stdout}'}), 500
    
    lines = [line.strip() for line in stdout.split('\n') if line.strip()]
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 4:
            size = parts[1]
            used = parts[2]
            free = parts[3]
            
            def to_mb(val):
                val = val.upper()
                try:
                    if val.endswith('G'):
                        return float(val[:-1]) * 1024
                    if val.endswith('M'):
                        return float(val[:-1])
                    if val.endswith('K'):
                        return float(val[:-1]) / 1024
                    return float(val)
                except ValueError:
                    return 0.0
            
            size_mb = to_mb(size)
            used_mb = to_mb(used)
            free_mb = to_mb(free)
            pct = (used_mb / size_mb * 100) if size_mb > 0 else 0
            
            return jsonify({
                'success': True,
                'size': size,
                'used': used,
                'free': free,
                'size_mb': size_mb,
                'used_mb': used_mb,
                'free_mb': free_mb,
                'percent': round(pct, 1)
            })
    
    return jsonify({'success': False, 'error': 'Failed to parse storage info'}), 500


@app.route('/api/device/media', methods=['GET'])
def device_media():
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'IP/Serial is required'}), 400
    target = get_adb_target(ip)
    stdout, stderr, code = run_adb(['-s', target, 'shell', 'ls', '-la', '/sdcard/frameo_files/media/'])
    if code != 0:
        return jsonify({'success': False, 'error': f'Failed to list media: {stderr or stdout}'}), 500
    
    media_files = []
    valid_exts = ('.jpeg', '.jpg', '.png', '.webp', '.mp4')
    for line in stdout.split('\n'):
        parts = line.split()
        if len(parts) >= 8:
            filename = parts[-1]
            if filename.lower().endswith(valid_exts):
                try:
                    size = int(parts[4])
                    date_str = f"{parts[5]} {parts[6]}"
                except (ValueError, IndexError):
                    size = 0
                    date_str = ""
                
                media_files.append({
                    'filename': filename,
                    'size': size,
                    'date': date_str,
                    'is_video': filename.lower().endswith('.mp4')
                })
    
    media_files.sort(key=lambda x: x['filename'], reverse=True)
    return jsonify({'success': True, 'files': media_files})


@app.route('/api/device/media/file/<filename>')
def serve_device_file(filename):
    ip = request.args.get('ip')
    if not ip:
        return "IP address is required", 400
    target = get_adb_target(ip)
    
    if filename.lower().endswith('.mp4'):
        mimetype = 'video/mp4'
    elif filename.lower().endswith(('.jpg', '.jpeg')):
        mimetype = 'image/jpeg'
    elif filename.lower().endswith('.png'):
        mimetype = 'image/png'
    elif filename.lower().endswith('.webp'):
        mimetype = 'image/webp'
    else:
        mimetype = 'application/octet-stream'
    
    def stream_file():
        cmd = ['adb', '-s', target, 'exec-out', 'cat', f'/sdcard/frameo_files/media/{filename}']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            while True:
                chunk = proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.kill()
            proc.wait()
            
    return Response(stream_file(), mimetype=mimetype)


@app.route('/api/device/media/delete', methods=['POST'])
def delete_device_file():
    data = request.json or {}
    ip = data.get('ip')
    filename = data.get('filename')
    if not ip or not filename:
        return jsonify({'success': False, 'error': 'IP and filename are required'}), 400
    
    target = get_adb_target(ip)
    if '/' in filename or '..' in filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
        
    stdout, stderr, code = run_adb(['-s', target, 'shell', 'rm', f'/sdcard/frameo_files/media/{filename}'])
    if code == 0:
        fav_file = os.path.join(app.root_path, 'favorites.json')
        if os.path.exists(fav_file):
            try:
                with open(fav_file, 'r') as f:
                    favs = json.load(f)
                if filename in favs:
                    favs.remove(filename)
                    with open(fav_file, 'w') as f:
                        json.dump(favs, f)
            except Exception:
                pass
                
        return jsonify({'success': True, 'message': f'Successfully deleted {filename}'})
    else:
        return jsonify({'success': False, 'error': stderr or stdout or 'Failed to delete file'})


@app.route('/api/device/favorites', methods=['GET', 'POST'])
def device_favorites():
    fav_file = os.path.join(app.root_path, 'favorites.json')
    if request.method == 'POST':
        data = request.json or {}
        filename = data.get('filename')
        action = data.get('action')
        if not filename or action not in ('add', 'remove'):
            return jsonify({'success': False, 'error': 'Invalid payload'}), 400
            
        favs = []
        if os.path.exists(fav_file):
            try:
                with open(fav_file, 'r') as f:
                    favs = json.load(f)
            except Exception:
                pass
                
        if action == 'add' and filename not in favs:
            favs.append(filename)
        elif action == 'remove' and filename in favs:
            favs.remove(filename)
            
        try:
            with open(fav_file, 'w') as f:
                json.dump(favs, f)
            return jsonify({'success': True, 'favorites': favs})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to write favorites: {e}'}), 500
    else:
        favs = []
        if os.path.exists(fav_file):
            try:
                with open(fav_file, 'r') as f:
                    favs = json.load(f)
            except Exception:
                pass
        return jsonify({'success': True, 'favorites': favs})


if __name__ == '__main__':
    # Try to open local address automatically
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:5001")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server on port 5001 (to avoid conflict with common services on 5000)
    app.run(host='0.0.0.0', port=5001, debug=False)
