"""Stealth configuration for anti-detection browser automation.

Provides rotating user-agents, stealth JavaScript injection scripts,
and Chromium launch arguments to minimize detection of automated browsing.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# User-Agent Pool — Modern Chrome versions on Mac/Win/Linux
# ---------------------------------------------------------------------------

USER_AGENTS: list[str] = [
    # Chrome 127 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome 127 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome 127 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome 126 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome 126 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome 126 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome 125 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 125 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 125 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 124 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 124 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 124 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def get_random_ua() -> str:
    """Return a random user-agent string from the pool.

    Each browser launch gets a different UA to avoid fingerprinting
    based on a single static user-agent.
    """
    return random.choice(USER_AGENTS)


# ---------------------------------------------------------------------------
# Stealth Chromium Launch Arguments
# ---------------------------------------------------------------------------

STEALTH_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-browser-side-navigation",
    "--disable-gpu",
    "--lang=en-US,en",
    "--disable-extensions",
    "--disable-default-apps",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-sync",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--no-first-run",
    "--password-store=basic",
    "--use-mock-keychain",
    "--export-tagged-pdf",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-client-side-phishing-detection",
    "--disable-component-extensions-with-background-pages",
]


# ---------------------------------------------------------------------------
# Stealth JavaScript Injection Scripts
# ---------------------------------------------------------------------------


def get_stealth_scripts() -> str:
    """Return JavaScript to inject into every page to hide automation indicators.

    Hides:
    - navigator.webdriver property
    - chrome.runtime presence indicating automation
    - Permissions API anomalies
    - Plugin/mime type discrepancies
    - WebGL renderer fingerprint masking
    - Language/platform consistency
    """
    return """
    // --- Hide navigator.webdriver ---
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });

    // --- Delete automation-related properties from navigator ---
    delete navigator.__proto__.webdriver;

    // --- Fix chrome.runtime to look like a real browser ---
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            PlatformOs: {
                MAC: 'mac',
                WIN: 'win',
                ANDROID: 'android',
                CROS: 'cros',
                LINUX: 'linux',
                OPENBSD: 'openbsd',
            },
            PlatformArch: {
                ARM: 'arm',
                X86_32: 'x86-32',
                X86_64: 'x86-64',
                MIPS: 'mips',
                MIPS64: 'mips64',
            },
            PlatformNaclArch: {
                ARM: 'arm',
                X86_32: 'x86-32',
                X86_64: 'x86-64',
                MIPS: 'mips',
                MIPS64: 'mips64',
            },
            RequestUpdateCheckStatus: {
                THROTTLED: 'throttled',
                NO_UPDATE: 'no_update',
                UPDATE_AVAILABLE: 'update_available',
            },
            OnInstalledReason: {
                INSTALL: 'install',
                UPDATE: 'update',
                CHROME_UPDATE: 'chrome_update',
                SHARED_MODULE_UPDATE: 'shared_module_update',
            },
            OnRestartRequiredReason: {
                APP_UPDATE: 'app_update',
                OS_UPDATE: 'os_update',
                PERIODIC: 'periodic',
            },
            connect: function() { return { onDisconnect: { addListener: function() {} } }; },
            sendMessage: function() {},
        };
    }

    // --- Fix Permissions API ---
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return originalQuery(parameters);
    };

    // --- Fix plugins array to look realistic ---
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
            ];
            plugins.length = 3;
            plugins.item = (i) => plugins[i] || null;
            plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
            plugins.refresh = () => {};
            return plugins;
        },
        configurable: true,
    });

    // --- Fix mimeTypes to match plugins ---
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => {
            const mimeTypes = [
                { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: { name: 'Chrome PDF Plugin' } },
                { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: { name: 'Chrome PDF Viewer' } },
            ];
            mimeTypes.length = 2;
            mimeTypes.item = (i) => mimeTypes[i] || null;
            mimeTypes.namedItem = (name) => mimeTypes.find(m => m.type === name) || null;
            return mimeTypes;
        },
        configurable: true,
    });

    // --- Fix languages to be consistent ---
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true,
    });

    // --- Prevent iframe detection of automation ---
    // Override contentWindow access patterns that detect Playwright
    const originalAttachShadow = Element.prototype.attachShadow;
    Element.prototype.attachShadow = function() {
        return originalAttachShadow.apply(this, arguments);
    };

    // --- Fix window.outerWidth/Height to match inner (headless indicator) ---
    if (window.outerWidth === 0) {
        Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
        Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
    }

    // --- Override toString to hide native code modifications ---
    const nativeToString = Function.prototype.toString;
    const overrides = new Map();

    function mockToString(fn, str) {
        overrides.set(fn, str);
    }

    Function.prototype.toString = function() {
        if (overrides.has(this)) {
            return overrides.get(this);
        }
        return nativeToString.call(this);
    };

    mockToString(Function.prototype.toString, 'function toString() { [native code] }');

    // --- Mask WebGL vendor/renderer to look like normal hardware ---
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37445) {
            return 'Intel Inc.';
        }
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37446) {
            return 'Intel Iris OpenGL Engine';
        }
        return getParameter.call(this, parameter);
    };

    // --- Prevent detection via connection rtt (headless often reports 0) ---
    if (navigator.connection && navigator.connection.rtt === 0) {
        Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    }

    // --- Prevent detection via hardware concurrency (headless may report unusual values) ---
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true,
    });

    // --- Prevent detection via deviceMemory ---
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true,
    });
    """
