"""Curated catalogue snapshots. Retail prices/availability are references, never live stock claims."""
CATALOG_CAPTURED_ON = "2026-11-27"

CURATED_LAPTOPS = [
    {
        "sku_id": "UX3405MA-PZ552WS", "brand": "ASUS", "model": "Zenbook 14 OLED",
        "retail_sku": "UX3405MA-PZ552WS", "processor": {"manufacturer": "Intel", "model": "Core Ultra 5 125H", "family": "Core Ultra Series 1", "cpu_cores": 14, "threads": 18, "npu_tops": 11},
        "gpu": "Intel Arc Graphics", "ram_gb": 16, "ram_type": "LPDDR5X", "storage_gb": 1024, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 14, "resolution": "2880x1800", "panel": "OLED", "refresh_hz": 120}, "weight_kg": 1.2, "battery_wh": 75,
        "price_inr": 94990, "price_kind": "MRP reference", "availability": "Retail stock not verified; check seller", "copilot_plus_eligible": False,
        "app_compatibility": {"architecture": "x86_64", "native": "Windows x64 applications", "caveat": "Application-specific GPU or NPU features still require compatible software and drivers."},
        "local_ai_verified": False, "limitation": "The processor NPU is rated at 11 TOPS; this is below the Copilot+ PC 40 TOPS NPU threshold.",
        "source_url": "https://www.asus.com/in/laptops/for-home/zenbook/asus-zenbook-14-oled-ux3405/techspec/", "price_source_url": "https://www.bajajfinserv.in/bmall/asus-zenbook-14-intel-core-ultra-5-16-gb-ram-1-tb-ssd-windows-11-home-14-inch-thin-and-light-laptop-ponder-blue-ux3405ma-pz552ws/p/29185", "source_checked_on": CATALOG_CAPTURED_ON,
    },
    {
        "sku_id": "X1607QA-MB050WS", "brand": "ASUS", "model": "Vivobook 16",
        "retail_sku": "X1607QA-MB050WS", "processor": {"manufacturer": "Qualcomm", "model": "Snapdragon X X1-26-100", "family": "Snapdragon X", "cpu_cores": 8, "threads": 8, "npu_tops": 45},
        "gpu": "Qualcomm Adreno GPU", "ram_gb": 16, "ram_type": "LPDDR5X", "storage_gb": 512, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 16, "resolution": "1920x1200", "panel": "IPS-level", "refresh_hz": 60}, "weight_kg": 1.88, "battery_wh": 50,
        "price_inr": 61990, "price_kind": "Observed ASUS Store offer", "availability": "Check delivery by pincode", "copilot_plus_eligible": True,
        "app_compatibility": {"architecture": "Arm64", "native": "Arm64 applications; Windows 11 Prism emulation supports many x86/x64 applications", "caveat": "Some kernel drivers, peripherals, anti-cheat and applications without Arm support may not work."},
        "local_ai_verified": False, "limitation": "Windows on Arm compatibility varies by app and driver; verify required specialist software before purchase.",
        "source_url": "https://in.store.asus.com/ai-powered-light-weight-laptop-asus-vivobook-16-x1607qa-mb050ws.html", "price_source_url": "https://in.store.asus.com/ai-powered-light-weight-laptop-asus-vivobook-16-x1607qa-mb050ws.html", "source_checked_on": CATALOG_CAPTURED_ON,
    },
    {
        "sku_id": "M1607KA-MB109WS", "brand": "ASUS", "model": "Vivobook 16",
        "retail_sku": "M1607KA-MB109WS", "processor": {"manufacturer": "AMD", "model": "Ryzen AI 7 350", "family": "Ryzen AI 300", "cpu_cores": 8, "threads": 16, "npu_tops": 50},
        "gpu": "AMD Radeon Graphics", "ram_gb": 16, "ram_type": "DDR5 (SO-DIMM expansion supported)", "storage_gb": 512, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 16, "resolution": "1920x1200", "panel": "IPS-level", "refresh_hz": 60}, "weight_kg": 1.88, "battery_wh": 42,
        "price_inr": 93990, "price_kind": "MRP reference", "availability": "ASUS Store showed out of stock when checked", "copilot_plus_eligible": True,
        "app_compatibility": {"architecture": "x86_64", "native": "Windows x64 applications", "caveat": "Individual AI features require supported software and drivers."},
        "local_ai_verified": False, "limitation": "The 42 Wh battery and 16-inch chassis trade battery capacity and portability against screen size; runtime depends on workload.",
        "source_url": "https://in.store.asus.com/asus-vivobook-16-m1607ka-mb109ws-copilot-pc.html", "price_source_url": "https://in.store.asus.com/asus-vivobook-16-m1607ka-mb109ws-copilot-pc.html", "source_checked_on": CATALOG_CAPTURED_ON,
    },
    {
        "sku_id": "UX5406SA-PZ7761WS", "brand": "ASUS", "model": "Zenbook S 14 OLED",
        "retail_sku": "UX5406SA-PZ7761WS", "processor": {"manufacturer": "Intel", "model": "Core Ultra 7 258V", "family": "Core Ultra 200V", "cpu_cores": 8, "threads": 8, "npu_tops": 47},
        "gpu": "Intel Arc Graphics", "ram_gb": 32, "ram_type": "LPDDR5X (on-package)", "storage_gb": 1024, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 14, "resolution": "2880x1800", "panel": "OLED touch", "refresh_hz": 120}, "weight_kg": 1.2, "battery_wh": 72,
        "price_inr": 182990, "price_kind": "MRP reference", "availability": "ASUS Store showed out of stock when checked", "copilot_plus_eligible": True,
        "app_compatibility": {"architecture": "x86_64", "native": "Windows x64 applications", "caveat": "Application-specific GPU or NPU features still require compatible software and drivers."},
        "local_ai_verified": False, "limitation": "The ASUS listing showed this exact configuration out of stock; ₹1,82,990 is its listed MRP, not a current offer or stock claim.",
        "source_url": "https://in.store.asus.com/rog/catalog/product/view/id/10443", "price_source_url": "https://in.store.asus.com/rog/catalog/product/view/id/10443", "source_checked_on": CATALOG_CAPTURED_ON,
    },
    {
        "sku_id": "S3407AA-SF058WS", "brand": "ASUS", "model": "Vivobook S 14",
        "retail_sku": "S3407AA-SF058WS", "processor": {"manufacturer": "Intel", "model": "Core Ultra 5 325", "family": "Core Ultra Series 3", "cpu_cores": 8, "threads": 8, "npu_tops": 47},
        "gpu": "Intel Graphics", "ram_gb": 16, "ram_type": "DDR5 (SO-DIMM expansion supported)", "storage_gb": 512, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 14, "resolution": "1920x1200", "panel": "OLED", "refresh_hz": 60}, "weight_kg": 1.4, "battery_wh": 70,
        "price_inr": 134990, "price_kind": "Observed ASUS Store offer", "availability": "Check delivery by pincode", "copilot_plus_eligible": True,
        "app_compatibility": {"architecture": "x86_64", "native": "Windows x64 applications", "caveat": "Application-specific GPU or NPU features still require compatible software and drivers."},
        "local_ai_verified": False, "limitation": "The listed 14-inch OLED panel is 60 Hz; the NPU specification does not establish that a particular local AI app is supported.",
        "source_url": "https://in.store.asus.com/rog/catalog/product/view/id/12459", "price_source_url": "https://in.store.asus.com/rog/catalog/product/view/id/12459", "source_checked_on": CATALOG_CAPTURED_ON,
    },
    {
        "sku_id": "UX5406AA-SU361WS", "brand": "ASUS", "model": "Zenbook S 14",
        "retail_sku": "UX5406AA-SU361WS", "processor": {"manufacturer": "Intel", "model": "Core Ultra 7 355", "family": "Core Ultra Series 3", "cpu_cores": 8, "threads": 8, "npu_tops": 49},
        "gpu": "Intel Graphics", "ram_gb": 16, "ram_type": "LPDDR5X (on-board)", "storage_gb": 512, "storage_type": "NVMe PCIe 4.0 SSD", "display": {"size_in": 14, "resolution": "2880x1800", "panel": "OLED touch", "refresh_hz": 120}, "weight_kg": 1.2, "battery_wh": 77,
        "price_inr": 171990, "price_kind": "Observed ASUS Store offer", "availability": "Check delivery by pincode", "copilot_plus_eligible": True,
        "app_compatibility": {"architecture": "x86_64", "native": "Windows x64 applications", "caveat": "Application-specific GPU or NPU features still require compatible software and drivers."},
        "local_ai_verified": False, "limitation": "Memory is 16 GB on-board; the product page describes it as on-board, so confirm upgradeability before buying.",
        "source_url": "https://in.store.asus.com/asus-zenbook-s14-ux5406aa-su361ws-copilot-pc.html", "price_source_url": "https://in.store.asus.com/asus-zenbook-s14-ux5406aa-su361ws-copilot-pc.html", "source_checked_on": CATALOG_CAPTURED_ON,
    },
]
