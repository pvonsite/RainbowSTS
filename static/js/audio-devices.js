/**
 * Audio device management
 */
class AudioDeviceManager {
    constructor() {
        this.devices = [];
        this.selectedDeviceId = '';
        this.deviceSelect = document.getElementById('audio-device');
        this.deviceInfoElement = document.getElementById('device-info');
        this.statusElement = document.getElementById('status');
        this.refreshDevicesBtn = document.getElementById('refresh-devices-btn');

        // Set up event listeners
        this.deviceSelect.addEventListener('change', () => this.onDeviceChange());
        this.refreshDevicesBtn.addEventListener('click', () => this.loadDevices());
    }

    async loadDevices() {
        try {
            this.statusElement.textContent = 'Status: Loading audio devices...';
            this.deviceSelect.innerHTML = '<option value="">Loading audio devices...</option>';

            // First, we need permission to access audio devices
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            // Stop the stream immediately after getting permission
            stream.getTracks().forEach(track => track.stop());

            // Now get the list of devices
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputDevices = devices.filter(device => device.kind === 'audioinput');
            this.devices = audioInputDevices;
            console.log('Audio devices:', audioInputDevices);

            // Clear the loading option
            this.deviceSelect.innerHTML = '';

            if (audioInputDevices.length === 0) {
                this.deviceSelect.innerHTML = '<option value="">No audio devices found</option>';
                this.deviceInfoElement.textContent = 'No audio input devices detected. Please check your microphone connection.';
                return;
            }

            // Categorize devices
            const virtualDevices = [];
            const physicalDevices = [];
            const otherDevices = [];

            // Keywords for identifying virtual devices like VB-Cable
            const virtualKeywords = ['vb-cable', 'vb cable', 'virtual', 'cable output', 'cable input', 'voicemeeter', 'vac'];

            audioInputDevices.forEach(device => {
                const label = device.label.toLowerCase() || '';
                if (virtualKeywords.some(keyword => label.includes(keyword))) {
                    virtualDevices.push(device);
                } else if (label.includes('default') || label.includes('communications')) {
                    otherDevices.push(device);
                } else {
                    physicalDevices.push(device);
                }
            });

            // Add virtual devices first (with group header)
            if (virtualDevices.length > 0) {
                const virtualGroup = document.createElement('optgroup');
                virtualGroup.label = 'Virtual Audio Devices (VB-Cable, etc.)';

                virtualDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    const label = device.label || `Virtual device ${device.deviceId.slice(0, 5)}...`;
                    option.textContent = label;
                    option.classList.add('virtual-device');
                    option.dataset.type = 'virtual';
                    virtualGroup.appendChild(option);
                });

                this.deviceSelect.appendChild(virtualGroup);
            }

            // Add physical devices
            if (physicalDevices.length > 0) {
                const physicalGroup = document.createElement('optgroup');
                physicalGroup.label = 'Physical Microphones';

                physicalDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    const label = device.label || `Microphone ${device.deviceId.slice(0, 5)}...`;
                    option.textContent = label;
                    option.classList.add('physical-device');
                    option.dataset.type = 'physical';
                    physicalGroup.appendChild(option);
                });

                this.deviceSelect.appendChild(physicalGroup);
            }

            // Add other devices
            if (otherDevices.length > 0) {
                const otherGroup = document.createElement('optgroup');
                otherGroup.label = 'System Devices';

                otherDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    const label = device.label || `Device ${device.deviceId.slice(0, 5)}...`;
                    option.textContent = label;
                    otherGroup.appendChild(option);
                });

                this.deviceSelect.appendChild(otherGroup);
            }

            // Automatically select VB-Cable or first virtual device if available
            const vbCableDevice = virtualDevices.find(d =>
                d.label.toLowerCase().includes('vb-cable') ||
                d.label.toLowerCase().includes('vb cable')
            );

            if (vbCableDevice) {
                this.deviceSelect.value = vbCableDevice.deviceId;
                this.selectedDeviceId = vbCableDevice.deviceId;
                this.updateDeviceInfo(vbCableDevice);
            } else if (virtualDevices.length > 0) {
                this.deviceSelect.value = virtualDevices[0].deviceId;
                this.selectedDeviceId = virtualDevices[0].deviceId;
                this.updateDeviceInfo(virtualDevices[0]);
            } else {
                this.deviceSelect.value = audioInputDevices[0].deviceId;
                this.selectedDeviceId = audioInputDevices[0].deviceId;
                this.updateDeviceInfo(audioInputDevices[0]);
            }

            this.statusElement.textContent = 'Status: Audio devices loaded';
        } catch (error) {
            console.error('Error accessing media devices:', error);
            this.deviceSelect.innerHTML = '<option value="">Error loading devices</option>';
            this.deviceInfoElement.textContent = 'Error accessing audio devices. Please ensure microphone permissions are granted.';
            this.statusElement.textContent = 'Status: Error loading audio devices';
        }
    }

    onDeviceChange() {
        this.selectedDeviceId = this.deviceSelect.value;
        const selectedDevice = this.devices.find(d => d.deviceId === this.selectedDeviceId);
        if (selectedDevice) {
            this.updateDeviceInfo(selectedDevice);
        }
    }

    updateDeviceInfo(device) {
        if (!device) return;

        const label = device.label.toLowerCase();
        const isVirtual = label.includes('vb-cable') ||
            label.includes('virtual') ||
            label.includes('voicemeeter') ||
            label.includes('cable output') ||
            label.includes('cable input');

        let deviceType = isVirtual ? 'Virtual Audio Device' : 'Physical Microphone';
        let additionalInfo = '';

        if (isVirtual) {
            if (label.includes('vb-cable') || label.includes('vb cable')) {
                additionalInfo = ' (Ideal for capturing audio from applications like Teams)';
            } else if (label.includes('voicemeeter')) {
                additionalInfo = ' (Voicemeeter virtual device)';
            }
        }

        if (device.label) {
            this.deviceInfoElement.innerHTML = `
                <strong>Selected Device:</strong> ${device.label} 
                <span class="badge ${isVirtual ? 'badge-virtual' : 'badge-physical'}">${deviceType}</span>
                ${additionalInfo}
            `;
        } else {
            this.deviceInfoElement.textContent = 'Device details not available until recording starts';
        }
    }

    getSelectedDeviceId() {
        return this.selectedDeviceId;
    }
}