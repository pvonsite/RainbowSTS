/**
 * Audio device management
 */
class AudioDeviceManager {
  devices = [];
  deviceGroups = {};
  selectedDevice = {
    input: "",
    output: "",
  };

  async loadDevices() {
    try {
      // First, we need permission to access audio devices
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop the stream immediately after getting permission
      stream.getTracks().forEach((track) => track.stop());

      // Now get the list of devices
      this.devices = await navigator.mediaDevices.enumerateDevices();
      console.log("Audio devices:", this.devices);

      // Categorize devices
      const virtualDevices = [];
      const physicalDevices = [];
      const otherDevices = [];

      // Keywords for identifying virtual devices like VB-Cable
      const virtualKeywords = [
        "vb-cable",
        "vb cable",
        "virtual",
        "cable output",
        "cable input",
        "voicemeeter",
        "vac",
      ];

      this.devices.forEach((device) => {
        const label = device.label.toLowerCase() || "";
        if (virtualKeywords.some((keyword) => label.includes(keyword))) {
          virtualDevices.push(device);
        } else if (
          label.includes("default") ||
          label.includes("communications")
        ) {
          otherDevices.push(device);
        } else {
          physicalDevices.push(device);
        }
      });

      this.deviceGroups = {
        virtual: virtualDevices,
        physical: physicalDevices,
        other: otherDevices,
      };
    } catch (error) {
      console.error("Error accessing media devices:", error);
    }
  }

  setDevice(kind, id) {
    this.selectedDevice[kind] = id;
    const selectedDevice = this.devices.find((d) => d.deviceId === id);
    if (selectedDevice) this.updateDeviceInfo(selectedDevice);
  }

  updateDeviceInfo(device) {
    if (!device) return;

    const label = device.label.toLowerCase();
    const isVirtual =
      label.includes("vb-cable") ||
      label.includes("virtual") ||
      label.includes("voicemeeter") ||
      label.includes("cable output") ||
      label.includes("cable input");

    let deviceType = isVirtual ? "Virtual Audio Device" : "Physical Microphone";
    let additionalInfo = "";

    if (isVirtual) {
      if (label.includes("vb-cable") || label.includes("vb cable")) {
        additionalInfo =
          " (Ideal for capturing audio from applications like Teams)";
      } else if (label.includes("voicemeeter")) {
        additionalInfo = " (Voicemeeter virtual device)";
      }
    }

    if (device.label) {
      this.deviceInfoElement.innerHTML = `
                <strong>Selected Device:</strong> ${device.label} 
                <span class="badge ${isVirtual ? "badge-virtual" : "badge-physical"}">${deviceType}</span>
                ${additionalInfo}
            `;
    } else {
      this.deviceInfoElement.textContent =
        "Device details not available until recording starts";
    }
  }

  getSelectedDeviceId() {
    return this.selectedDeviceId;
  }
}

