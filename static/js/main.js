document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const ipAddressInput = document.getElementById('ip-address');
    const btnConnect = document.getElementById('btn-connect');
    const btnDisconnect = document.getElementById('btn-disconnect');
    const btnScan = document.getElementById('btn-scan');
    const scanResultsContainer = document.getElementById('scan-results-container');
    const scanResultsList = document.getElementById('scan-results-list');
    
    const btnToggleGuide = document.getElementById('btn-toggle-guide');
    const guideContent = document.getElementById('guide-content');
    const btnSetupWireless = document.getElementById('btn-setup-wireless');
    
    const consoleBox = document.getElementById('console-box');
    const btnClearLogs = document.getElementById('btn-clear-logs');
    
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const folderInput = document.getElementById('folder-input');
    const previewSection = document.getElementById('preview-section');
    const previewGrid = document.getElementById('preview-grid');
    const fileCountSpan = document.getElementById('file-count');
    const btnClearFiles = document.getElementById('btn-clear-files');
    
    const progressBarContainer = document.getElementById('progress-bar-container');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');
    const progressFill = document.getElementById('progress-fill');
    
    const btnSend = document.getElementById('btn-send');
    const btnAutomateImport = document.getElementById('btn-automate-import');
    
    // Tabs & Local Sync selectors
    const tabBtnBeam = document.getElementById('tab-btn-beam');
    const tabBtnSync = document.getElementById('tab-btn-sync');
    const tabContentBeam = document.getElementById('tab-content-beam');
    const tabContentSync = document.getElementById('tab-content-sync');
    const localFolderPathInput = document.getElementById('local-folder-path');
    const btnBrowseLocal = document.getElementById('btn-browse-local');
    const btnSyncAction = document.getElementById('btn-sync-action');
    const syncStatusBox = document.getElementById('sync-status-box');
    const syncStatusText = document.getElementById('sync-status-text');
    
    // Gallery & Storage selectors
    const tabBtnGallery = document.getElementById('tab-btn-gallery');
    const tabContentGallery = document.getElementById('tab-content-gallery');
    const storageUsageText = document.getElementById('storage-usage-text');
    const storageFill = document.getElementById('storage-fill');
    const chkFavoritesOnly = document.getElementById('chk-favorites-only');
    const btnRefreshGallery = document.getElementById('btn-refresh-gallery');
    const deviceGalleryGrid = document.getElementById('device-gallery-grid');
    
    const chkOptimize = document.getElementById('chk-optimize');
    const optResolution = document.getElementById('opt-resolution');
    const optFit = document.getElementById('opt-fit');
    const optimizationSettings = document.getElementById('optimization-settings');
    
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('status-text');
    const toast = document.getElementById('toast');

    // State Variables
    let selectedFiles = [];
    let isConnected = false;
    let isAuthorized = false;
    let checkStatusInterval = null;
    let activeIp = localStorage.getItem('frameo_ip') || '';

    // Initialize UI
    if (activeIp) {
        ipAddressInput.value = activeIp;
    }

    chkOptimize.addEventListener('change', () => {
        if (chkOptimize.checked) {
            optimizationSettings.classList.remove('disabled');
            log('Image optimization enabled.', 'system');
        } else {
            optimizationSettings.classList.add('disabled');
            log('Image optimization disabled. Images will be pushed in original size.', 'warning');
        }
    });

    // Log to custom console
    function log(message, type = 'system') {
        const line = document.createElement('div');
        line.className = `log-line ${type}-log`;
        
        const timestamp = new Date().toLocaleTimeString();
        line.innerText = `[${timestamp}] ${message}`;
        
        consoleBox.appendChild(line);
        consoleBox.scrollTop = consoleBox.scrollHeight;
    }

    // Toast Notification helper
    function showToast(message, type = 'success') {
        toast.innerText = message;
        toast.className = `toast toast-${type}`;
        toast.classList.remove('hidden');
        
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 4000);
    }

    // Connection Status Check
    async function checkStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            const devices = data.devices || [];
            
            // If we have an active IP, check its status in the list
            if (activeIp) {
                const isUsbSerial = !activeIp.includes('.') && !activeIp.includes(':');
                const target = isUsbSerial ? activeIp : (activeIp.includes(':') ? activeIp : `${activeIp}:5555`);
                const dev = devices.find(d => d.id === target || d.id.startsWith(activeIp));
                
                if (dev) {
                    isConnected = true;
                    if (dev.state === 'device') {
                        isAuthorized = true;
                        updateStatusUI('online', `Connected (${activeIp})`);
                    } else if (dev.state === 'unauthorized') {
                        isAuthorized = false;
                        updateStatusUI('unauthorized', 'Unauthorized (Trust Mac on Screen)');
                    } else {
                        isAuthorized = false;
                        updateStatusUI('connecting', `Device State: ${dev.state}`);
                    }
                } else {
                    isConnected = false;
                    isAuthorized = false;
                    updateStatusUI('offline', 'Disconnected');
                }
            } else {
                if (devices.length > 0) {
                    const firstDev = devices[0];
                    updateStatusUI(
                        firstDev.state === 'device' ? 'online' : 'unauthorized', 
                        `Detected: ${firstDev.id} (${firstDev.state})`
                    );
                    isConnected = true;
                    isAuthorized = firstDev.state === 'device';
                    activeIp = firstDev.id.split(':')[0];
                    ipAddressInput.value = activeIp;
                } else {
                    isConnected = false;
                    isAuthorized = false;
                    updateStatusUI('offline', 'Disconnected');
                }
            }
        } catch (error) {
            console.error('Error checking status:', error);
        } finally {
            updateControlsState();
        }
    }

    function updateStatusUI(state, text) {
        statusDot.className = 'status-dot';
        statusDot.classList.add(`dot-${state}`);
        statusText.innerText = text;
    }

    function updateControlsState() {
        const canSend = isConnected && isAuthorized && selectedFiles.length > 0;
        btnSend.disabled = !canSend;
        btnAutomateImport.disabled = !(isConnected && isAuthorized);
        btnDisconnect.disabled = !isConnected;
        
        // Sync local folder check
        const path = localFolderPathInput.value.trim();
        const canSync = isConnected && isAuthorized && path.length > 0;
        btnSyncAction.disabled = !canSync;
        
        // Gallery Refresh check
        btnRefreshGallery.disabled = !(isConnected && isAuthorized);
        
        if (isConnected) {
            btnConnect.innerText = 'Connected';
            btnConnect.classList.remove('btn-primary');
            btnConnect.classList.add('btn-secondary');
        } else {
            btnConnect.innerText = 'Connect';
            btnConnect.classList.remove('btn-secondary');
            btnConnect.classList.add('btn-primary');
        }
    }

    // Periodically poll connection status
    checkStatus();
    checkStatusInterval = setInterval(checkStatus, 3000);

    // Connect Button Action
    btnConnect.addEventListener('click', async () => {
        const ip = ipAddressInput.value.trim();
        if (!ip) {
            showToast('Please enter an IP address', 'error');
            return;
        }

        activeIp = ip;
        localStorage.setItem('frameo_ip', ip);
        log(`Attempting to connect to ${ip}...`, 'info');
        updateStatusUI('connecting', 'Connecting...');
        btnConnect.disabled = true;

        try {
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip })
            });
            const data = await response.json();
            
            if (data.success) {
                log(`ADB Output: ${data.message}`, 'success');
                if (data.device_state === 'unauthorized') {
                    log('Device is connected but UNAUTHORIZED. Tap "Allow USB Debugging" on the frame screen.', 'warning');
                    showToast('Trust computer on frame screen!', 'error');
                } else {
                    log(`Successfully connected and authorized to ${ip}`, 'success');
                    showToast('Connected to frame!', 'success');
                }
                checkStatus();
            } else {
                log(`Connection failed: ${data.error}`, 'error');
                showToast('Connection failed', 'error');
            }
        } catch (error) {
            log(`Network Error: ${error.message}`, 'error');
        } finally {
            btnConnect.disabled = false;
            updateControlsState();
        }
    });

    // Disconnect Button Action
    btnDisconnect.addEventListener('click', async () => {
        if (!activeIp) return;
        
        log(`Disconnecting from ${activeIp}...`, 'info');
        try {
            const response = await fetch('/api/disconnect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip: activeIp })
            });
            const data = await response.json();
            if (data.success) {
                log(`Disconnected: ${data.message}`, 'success');
                showToast('Disconnected from device', 'info');
                activeIp = '';
                localStorage.removeItem('frameo_ip');
                ipAddressInput.value = '';
                checkStatus();
            }
        } catch (error) {
            log(`Error: ${error.message}`, 'error');
        }
    });

    // Network Scanner Action
    btnScan.addEventListener('click', async () => {
        log('Scanning local network subnet for ADB devices...', 'info');
        btnScan.disabled = true;
        btnScan.innerHTML = '<span class="icon">⌛</span> Scanning...';
        scanResultsContainer.classList.add('hidden');
        scanResultsList.innerHTML = '';

        try {
            const response = await fetch('/api/scan');
            const data = await response.json();
            const ips = data.found_ips || [];
            
            log(`Scan complete. Found ${ips.length} potential ADB device(s).`, 'success');
            
            if (ips.length > 0) {
                scanResultsContainer.classList.remove('hidden');
                ips.forEach(ip => {
                    const li = document.createElement('li');
                    li.innerHTML = `<span class="scan-ip">${ip}</span> <span class="scan-action">Connect</span>`;
                    li.addEventListener('click', () => {
                        ipAddressInput.value = ip;
                        btnConnect.click();
                    });
                    scanResultsList.appendChild(li);
                });
                showToast(`Found ${ips.length} device(s)!`, 'success');
            } else {
                showToast('No active ADB devices found. Ensure wireless debugging is enabled.', 'info');
                log('No devices responding on port 5555. Check first-time setup guide.', 'warning');
            }
        } catch (error) {
            log(`Scan failed: ${error.message}`, 'error');
        } finally {
            btnScan.disabled = false;
            btnScan.innerHTML = '<span class="icon">🔍</span> Scan Subnet';
        }
    });

    // Toggle Setup Guide
    btnToggleGuide.addEventListener('click', () => {
        if (guideContent.classList.contains('collapsed')) {
            guideContent.classList.remove('collapsed');
            btnToggleGuide.innerText = 'Hide';
        } else {
            guideContent.classList.add('collapsed');
            btnToggleGuide.innerText = 'Show';
        }
    });

    // USB Wireless Setup Action
    btnSetupWireless.addEventListener('click', async () => {
        log('Attempting to trigger Wireless ADB over USB...', 'info');
        try {
            const response = await fetch('/api/setup-wireless', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                log(data.message, 'success');
                showToast('Wireless port opened!', 'success');
            } else {
                log(data.error, 'error');
                showToast(data.error, 'error');
            }
        } catch (error) {
            log(`Error: ${error.message}`, 'error');
        }
    });

    // Clear System Logs
    btnClearLogs.addEventListener('click', () => {
        consoleBox.innerHTML = '';
        log('Logs cleared.', 'system');
    });

    // File Upload Area Trigger
    uploadZone.addEventListener('click', (e) => {
        if (e.target.id === 'link-folder' || e.target.id === 'link-files') {
            return;
        }
        fileInput.click();
    });

    document.getElementById('link-files').addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    document.getElementById('link-folder').addEventListener('click', (e) => {
        e.stopPropagation();
        folderInput.click();
    });

    // Drag and Drop styling
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
        }, false);
    });

    uploadZone.addEventListener('drop', async (e) => {
        const items = e.dataTransfer.items;
        if (items) {
            log('Processing dropped items (folders/files)...', 'system');
            const entries = [];
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const entry = item.webkitGetAsEntry();
                    if (entry) {
                        entries.push(entry);
                    }
                }
            }

            // Async helper to traverse files recursively
            async function traverse(entry) {
                if (entry.isFile) {
                    const file = await new Promise((resolve, reject) => {
                        entry.file(resolve, reject);
                    });
                    handleFiles([file]);
                } else if (entry.isDirectory) {
                    const reader = entry.createReader();
                    const readAllEntries = async () => {
                        let allEntries = [];
                        let batch = await new Promise((resolve) => reader.readEntries(resolve));
                        while (batch.length > 0) {
                            allEntries = allEntries.concat(batch);
                            batch = await new Promise((resolve) => reader.readEntries(resolve));
                        }
                        return allEntries;
                    };
                    const subEntries = await readAllEntries();
                    for (const subEntry of subEntries) {
                        await traverse(subEntry);
                    }
                }
            }

            for (const entry of entries) {
                await traverse(entry);
            }
        } else {
            handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    folderInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Handle selected files
    function handleFiles(files) {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            // Check file type
            if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
                log(`Skipped unsupported file: ${file.name}`, 'warning');
                continue;
            }
            
            // Prevent duplicates
            if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
                continue;
            }

            selectedFiles.push(file);
        }

        renderPreviews();
        updateControlsState();
    }

    // Render Preview Thumbnails
    function renderPreviews() {
        previewGrid.innerHTML = '';
        
        if (selectedFiles.length === 0) {
            previewSection.classList.add('hidden');
            fileCountSpan.innerText = '0';
            return;
        }

        previewSection.classList.remove('hidden');
        fileCountSpan.innerText = selectedFiles.length;

        selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'preview-item';
            
            const btnRemove = document.createElement('button');
            btnRemove.className = 'btn-remove';
            btnRemove.innerHTML = '&times;';
            btnRemove.setAttribute('aria-label', `Remove ${file.name}`);
            btnRemove.addEventListener('click', (e) => {
                e.stopPropagation();
                selectedFiles.splice(index, 1);
                renderPreviews();
                updateControlsState();
            });

            const details = document.createElement('div');
            details.className = 'preview-details';
            details.innerHTML = `${file.name}<br><span class="preview-size">${(file.size / (1024 * 1024)).toFixed(2)} MB</span>`;

            item.appendChild(btnRemove);

            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.className = 'preview-image';
                img.alt = file.name;
                
                // Lazy thumbnail creation
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);
                item.appendChild(img);
            } else if (file.type.startsWith('video/')) {
                const video = document.createElement('video');
                video.className = 'preview-video';
                video.muted = true;
                
                // Show simple icon/badge for video preview
                const badge = document.createElement('div');
                badge.className = 'video-badge';
                badge.innerHTML = '🎥 Video';
                item.appendChild(badge);
                
                const url = URL.createObjectURL(file);
                video.src = url;
                video.currentTime = 1; // Attempt to load frame at 1s
                item.appendChild(video);
            }

            item.appendChild(details);
            previewGrid.appendChild(item);
        });
    }

    // Remove All Selected Files
    btnClearFiles.addEventListener('click', () => {
        selectedFiles = [];
        renderPreviews();
        updateControlsState();
        log('Selected files cleared.', 'system');
    });

    // Send Files to Frameo
    btnSend.addEventListener('click', () => {
        if (selectedFiles.length === 0 || !activeIp) return;
        
        btnSend.disabled = true;
        btnAutomateImport.disabled = true;
        btnClearFiles.disabled = true;
        progressBarContainer.classList.remove('hidden');
        
        const formData = new FormData();
        formData.append('ip', activeIp);
        
        const optimize = chkOptimize.checked;
        const resolution = optResolution.value;
        const fitMode = optFit.value;
        const [width, height] = resolution.split('x');
        
        formData.append('optimize', optimize);
        formData.append('width', width);
        formData.append('height', height);
        formData.append('fit_mode', fitMode);
        
        selectedFiles.forEach(file => {
            formData.append('files', file);
        });

        log(`Sending ${selectedFiles.length} file(s) to Frameo at ${activeIp}...`, 'info');
        
        const xhr = new XMLHttpRequest();
        
        // Progress tracking
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = `${percent}%`;
                progressPercent.innerText = `${percent}%`;
                
                if (percent === 100) {
                    progressStatus.innerText = 'ADB Pushing to Frame storage...';
                    log('Files uploaded to server. Pushing files to Frameo storage over ADB...', 'info');
                } else {
                    progressStatus.innerText = `Uploading files to server: ${percent}%`;
                }
            }
        });

        xhr.onload = function() {
            progressBarContainer.classList.add('hidden');
            btnSend.disabled = false;
            btnClearFiles.disabled = false;
            updateControlsState();

            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                if (response.success) {
                    log(`Successfully transferred ${response.success_count}/${response.total_count} files!`, 'success');
                    if (response.media_scan.success) {
                        log('System media scan triggered successfully.', 'success');
                    } else {
                        log('System media scan failed, but files were pushed. Try restarting the frame if files do not show up.', 'warning');
                    }
                    
                    showToast(`Sent ${response.success_count} files successfully!`, 'success');
                    
                    // Clear file selections on success
                    selectedFiles = [];
                    renderPreviews();
                } else {
                    log('File transfer completed with errors.', 'error');
                    response.results.forEach(res => {
                        if (res.status === 'failed') {
                            log(`Failed to push ${res.file}: ${res.error}`, 'error');
                        }
                    });
                    showToast('Some files failed to send.', 'error');
                }
            } else {
                let errMsg = 'Server error occurred.';
                try {
                    const response = JSON.parse(xhr.responseText);
                    errMsg = response.error || errMsg;
                } catch(e) {}
                log(`Error: ${errMsg}`, 'error');
                showToast(errMsg, 'error');
            }
        };

        xhr.onerror = function() {
            progressBarContainer.classList.add('hidden');
            btnSend.disabled = false;
            btnClearFiles.disabled = false;
            updateControlsState();
            log('XHR request failed.', 'error');
            showToast('Failed to send request.', 'error');
        };

        xhr.open('POST', '/api/send', true);
        xhr.send(formData);
    });

    // Automate Import button
    btnAutomateImport.addEventListener('click', async () => {
        if (!activeIp) return;
        
        log('Starting automated import click sequence on device screen...', 'accent');
        btnAutomateImport.disabled = true;
        btnAutomateImport.innerText = '🤖 Running...';
        
        try {
            const response = await fetch('/api/automate-import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip: activeIp })
            });
            const data = await response.json();
            
            // Print all backend automation logs
            if (data.logs && data.logs.length > 0) {
                data.logs.forEach(msg => log(`[UI Auto] ${msg}`, 'info'));
            }
            
            if (data.success) {
                log(`Automation result: ${data.message}`, 'success');
                showToast(data.message, 'success');
            } else {
                log(`Automation failed: ${data.error}`, 'error');
                showToast('Automation failed. Check frame screen.', 'error');
            }
        } catch (error) {
            log(`Automation Request Error: ${error.message}`, 'error');
        } finally {
            btnAutomateImport.innerText = '🤖 Automate Import';
            updateControlsState();
        }
    });

    // Tab switching logic
    tabBtnBeam.addEventListener('click', () => {
        tabBtnBeam.classList.add('active');
        tabBtnSync.classList.remove('active');
        tabBtnGallery.classList.remove('active');
        tabContentBeam.classList.remove('hidden');
        tabContentSync.classList.add('hidden');
        tabContentGallery.classList.add('hidden');
        btnSend.classList.remove('hidden');
        btnSyncAction.classList.add('hidden');
        updateControlsState();
    });

    tabBtnSync.addEventListener('click', () => {
        tabBtnSync.classList.add('active');
        tabBtnBeam.classList.remove('active');
        tabBtnGallery.classList.remove('active');
        tabContentSync.classList.remove('hidden');
        tabContentBeam.classList.add('hidden');
        tabContentGallery.classList.add('hidden');
        btnSend.classList.add('hidden');
        btnSyncAction.classList.remove('hidden');
        updateControlsState();
    });

    tabBtnGallery.addEventListener('click', () => {
        tabBtnGallery.classList.add('active');
        tabBtnBeam.classList.remove('active');
        tabBtnSync.classList.remove('active');
        tabContentGallery.classList.remove('hidden');
        tabContentBeam.classList.add('hidden');
        tabContentSync.classList.add('hidden');
        btnSend.classList.add('hidden');
        btnSyncAction.classList.add('hidden');
        updateControlsState();
        
        if (isConnected && isAuthorized) {
            refreshStorageInfo();
            refreshDeviceGallery();
        }
    });

    // Browse Local Folder action
    btnBrowseLocal.addEventListener('click', async () => {
        log('Opening native macOS folder picker...', 'info');
        btnBrowseLocal.disabled = true;
        try {
            const response = await fetch('/api/browse-folder', { method: 'POST' });
            const data = await response.json();
            if (data.success && data.path) {
                localFolderPathInput.value = data.path;
                log(`Selected folder: ${data.path}`, 'success');
            } else {
                log('Folder selection cancelled or failed.', 'warning');
            }
        } catch (err) {
            log(`Error opening folder dialog: ${err.message}`, 'error');
        } finally {
            btnBrowseLocal.disabled = false;
            updateControlsState();
        }
    });

    localFolderPathInput.addEventListener('input', () => {
        updateControlsState();
    });

    // SSE Folder Sync Action
    let syncEventSource = null;
    btnSyncAction.addEventListener('click', () => {
        const path = localFolderPathInput.value.trim();
        if (!path) return;

        // Reset progress UI
        progressBarContainer.classList.remove('hidden');
        progressStatus.innerText = 'Initializing sync...';
        progressPercent.innerText = '0%';
        progressFill.style.width = '0%';
        
        syncStatusBox.classList.remove('hidden');
        syncStatusText.innerText = 'Connecting to sync stream...\n';

        btnSyncAction.disabled = true;
        btnAutomateImport.disabled = true;
        
        const optimize = chkOptimize.checked;
        const resolution = optResolution.value;
        const [w, h] = resolution.split('x');
        const fit = optFit.value;
        
        const url = `/api/sync-stream?path=${encodeURIComponent(path)}&ip=${encodeURIComponent(activeIp)}&optimize=${optimize}&width=${w}&height=${h}&fit_mode=${fit}`;
        
        if (syncEventSource) {
            syncEventSource.close();
        }
        
        syncEventSource = new EventSource(url);
        
        syncEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.type === 'status') {
                log(data.message, 'info');
                syncStatusText.innerText += `${data.message}\n`;
                progressStatus.innerText = data.message;
            } else if (data.type === 'progress') {
                const percent = Math.round((data.current / data.total) * 100);
                progressStatus.innerText = `Processing: ${data.file}`;
                progressPercent.innerText = `${percent}%`;
                progressFill.style.width = `${percent}%`;
                
                syncStatusText.innerText = `Syncing... [${data.current}/${data.total}]\nFile: ${data.file}\n`;
            } else if (data.type === 'log') {
                log(data.message, data.level || 'info');
                syncStatusText.innerText += `[Log] ${data.message}\n`;
            } else if (data.type === 'error') {
                log(`Sync Error: ${data.message}`, 'error');
                syncStatusText.innerText += `Error: ${data.message}\n`;
                showToast(`Sync error: ${data.message}`, 'error');
                cleanupSync();
            } else if (data.type === 'complete') {
                log(data.message, 'success');
                syncStatusText.innerText += `\n${data.message}\n`;
                progressStatus.innerText = 'Sync completed!';
                progressPercent.innerText = '100%';
                progressFill.style.width = '100%';
                showToast('Folder synced successfully!', 'success');
                cleanupSync();
            }
        };
        
        syncEventSource.onerror = function() {
            log('Sync connection closed or lost.', 'warning');
            cleanupSync();
        };
        
        function cleanupSync() {
            if (syncEventSource) {
                syncEventSource.close();
                syncEventSource = null;
            }
            btnSyncAction.disabled = false;
            updateControlsState();
        }
    });

    // Gallery & Storage functionality
    let cachedFavorites = [];
    let cachedDeviceFiles = [];

    async function refreshStorageInfo() {
        if (!activeIp) return;
        try {
            const response = await fetch(`/api/device/storage?ip=${encodeURIComponent(activeIp)}`);
            const data = await response.json();
            if (data.success) {
                storageUsageText.innerText = `${data.used} of ${data.size} used (${data.free} free)`;
                storageFill.style.width = `${data.percent}%`;
            } else {
                storageUsageText.innerText = 'Failed to read storage';
            }
        } catch (err) {
            storageUsageText.innerText = 'Error reading storage';
        }
    }

    async function refreshDeviceGallery() {
        if (!activeIp) return;
        
        deviceGalleryGrid.innerHTML = '<p class="empty-state">Loading gallery from device...</p>';
        
        try {
            // 1. Fetch favorites
            const favResp = await fetch('/api/device/favorites');
            const favData = await favResp.json();
            cachedFavorites = favData.success ? favData.favorites : [];
            
            // 2. Fetch device media
            const mediaResp = await fetch(`/api/device/media?ip=${encodeURIComponent(activeIp)}`);
            const mediaData = await mediaResp.json();
            if (mediaData.success) {
                cachedDeviceFiles = mediaData.files;
                renderDeviceGalleryGrid();
            } else {
                deviceGalleryGrid.innerHTML = `<p class="empty-state error-text">Failed to fetch files: ${mediaData.error}</p>`;
            }
        } catch (err) {
            deviceGalleryGrid.innerHTML = `<p class="empty-state error-text">Error loading gallery: ${err.message}</p>`;
        }
    }

    function renderDeviceGalleryGrid() {
        const favoritesOnly = chkFavoritesOnly.checked;
        let files = cachedDeviceFiles;
        
        if (favoritesOnly) {
            files = files.filter(f => cachedFavorites.includes(f.filename));
        }
        
        if (files.length === 0) {
            deviceGalleryGrid.innerHTML = `<p class="empty-state">${favoritesOnly ? 'No favorites found.' : 'No photos or videos on the frame.'}</p>`;
            return;
        }
        
        deviceGalleryGrid.innerHTML = '';
        files.forEach(file => {
            const card = document.createElement('div');
            card.className = 'device-media-card';
            
            const isFav = cachedFavorites.includes(file.filename);
            const thumbUrl = `/api/device/media/file/${file.filename}?ip=${encodeURIComponent(activeIp)}`;
            
            card.innerHTML = `
                <img class="device-media-thumb" src="${thumbUrl}" alt="${file.filename}" loading="lazy">
                ${file.is_video ? '<div class="video-badge">▶</div>' : ''}
                <div class="device-media-actions">
                    <button class="card-action-btn favorite-btn ${isFav ? 'is-favorite' : ''}" title="Favorite">
                        ${isFav ? '★' : '☆'}
                    </button>
                    <button class="card-action-btn delete-btn" title="Delete">
                        🗑️
                    </button>
                </div>
            `;
            
            // Toggle favorite event
            const favBtn = card.querySelector('.favorite-btn');
            favBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const action = isFav ? 'remove' : 'add';
                favBtn.disabled = true;
                try {
                    const resp = await fetch('/api/device/favorites', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename: file.filename, action })
                    });
                    const data = await resp.json();
                    if (data.success) {
                        cachedFavorites = data.favorites;
                        log(`${isFav ? 'Removed from' : 'Added to'} favorites: ${file.filename}`, 'success');
                        renderDeviceGalleryGrid();
                    } else {
                        showToast('Failed to update favorites', 'error');
                    }
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    favBtn.disabled = false;
                }
            });
            
            // Delete event
            const delBtn = card.querySelector('.delete-btn');
            delBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (!confirm(`Are you sure you want to delete ${file.filename} from the frame? This action is permanent.`)) {
                    return;
                }
                
                log(`Deleting ${file.filename} from device...`, 'info');
                delBtn.disabled = true;
                try {
                    const resp = await fetch('/api/device/media/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ip: activeIp, filename: file.filename })
                    });
                    const data = await resp.json();
                    if (data.success) {
                        log(`Deleted file: ${file.filename}`, 'success');
                        showToast('File deleted successfully', 'success');
                        
                        cachedDeviceFiles = cachedDeviceFiles.filter(f => f.filename !== file.filename);
                        cachedFavorites = cachedFavorites.filter(f => f !== file.filename);
                        
                        renderDeviceGalleryGrid();
                        refreshStorageInfo();
                    } else {
                        log(`Failed to delete: ${data.error}`, 'error');
                        showToast(`Failed to delete: ${data.error}`, 'error');
                    }
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    delBtn.disabled = false;
                }
            });
            
            deviceGalleryGrid.appendChild(card);
        });
    }

    btnRefreshGallery.addEventListener('click', () => {
        if (isConnected && isAuthorized) {
            refreshStorageInfo();
            refreshDeviceGallery();
        }
    });

    chkFavoritesOnly.addEventListener('change', () => {
        renderDeviceGalleryGrid();
    });
});
