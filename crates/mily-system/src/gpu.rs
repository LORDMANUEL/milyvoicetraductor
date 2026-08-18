use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "kind")]
pub enum GpuVendor {
    Intel,
    Nvidia,
    Amd,
    Microsoft,
    Other { vendor_id: u32 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GpuAdapterInfo {
    pub name: String,
    pub vendor: GpuVendor,
    pub vendor_id: u32,
    pub device_id: u32,
    pub dedicated_video_memory_mb: u64,
    pub shared_system_memory_mb: u64,
    pub software: bool,
}

pub fn classify_gpu_vendor(vendor_id: u32) -> GpuVendor {
    match vendor_id {
        0x8086 => GpuVendor::Intel,
        0x10DE => GpuVendor::Nvidia,
        0x1002 => GpuVendor::Amd,
        0x1414 => GpuVendor::Microsoft,
        value => GpuVendor::Other { vendor_id: value },
    }
}

pub fn gpu_inventory() -> Vec<GpuAdapterInfo> {
    platform_gpu_inventory()
}

#[cfg(not(windows))]
fn platform_gpu_inventory() -> Vec<GpuAdapterInfo> {
    Vec::new()
}

#[cfg(windows)]
fn platform_gpu_inventory() -> Vec<GpuAdapterInfo> {
    use windows::Win32::Graphics::Dxgi::{
        CreateDXGIFactory1, DXGI_ADAPTER_DESC1, DXGI_ADAPTER_FLAG_NONE, DXGI_ADAPTER_FLAG_SOFTWARE,
        IDXGIFactory1,
    };

    let factory: IDXGIFactory1 = match unsafe { CreateDXGIFactory1() } {
        Ok(factory) => factory,
        Err(_) => return Vec::new(),
    };

    let mut adapters = Vec::new();
    for index in 0.. {
        let adapter = match unsafe { factory.EnumAdapters1(index) } {
            Ok(adapter) => adapter,
            Err(_) => break,
        };

        let mut desc = DXGI_ADAPTER_DESC1::default();
        if unsafe { adapter.GetDesc1(&mut desc) }.ok().is_err() {
            continue;
        }

        let description_length = desc
            .Description
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(desc.Description.len());
        let name = String::from_utf16_lossy(&desc.Description[..description_length]);
        let software = (desc.Flags as i32 & DXGI_ADAPTER_FLAG_SOFTWARE) != DXGI_ADAPTER_FLAG_NONE;

        adapters.push(GpuAdapterInfo {
            name: if name.trim().is_empty() {
                format!("GPU {:04X}:{:04X}", desc.VendorId, desc.DeviceId)
            } else {
                name
            },
            vendor: classify_gpu_vendor(desc.VendorId),
            vendor_id: desc.VendorId,
            device_id: desc.DeviceId,
            dedicated_video_memory_mb: desc.DedicatedVideoMemory as u64 / 1024 / 1024,
            shared_system_memory_mb: desc.SharedSystemMemory as u64 / 1024 / 1024,
            software,
        });
    }

    adapters
}
