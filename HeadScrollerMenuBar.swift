import Cocoa

struct Settings: Codable {
    var sensitivity: Double
    var deadzone: Double
    var cam: Int

    static let defaults = Settings(sensitivity: 10.0, deadzone: 0.04, cam: 1)
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var process: Process?
    var previewProcess: Process?
    var isTracking = false
    var showingPreview = false
    var toggleItem: NSMenuItem!
    var previewItem: NSMenuItem!
    var statusLabel: NSMenuItem!
    var timer: Timer?
    var settings: Settings = .defaults

    // Sensitivity/deadzone menu items so we can update checkmarks
    var sensItems: [NSMenuItem] = []
    var dzItems: [NSMenuItem] = []

    let baseDir: String = {
        if let resourcePath = Bundle.main.resourcePath,
           FileManager.default.fileExists(atPath: (resourcePath as NSString).appendingPathComponent("headscroller.py")) {
            return resourcePath
        }
        return (CommandLine.arguments[0] as NSString).deletingLastPathComponent
    }()

    let dataDir: String = {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("HeadScroller").path
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        return dir
    }()

    var scriptPath: String { (baseDir as NSString).appendingPathComponent("headscroller.py") }
    var settingsPath: String { (dataDir as NSString).appendingPathComponent("settings.json") }
    var logPath: String { (dataDir as NSString).appendingPathComponent("headscroller.log") }

    func loadSettings() {
        let url = URL(fileURLWithPath: settingsPath)
        guard let data = try? Data(contentsOf: url),
              let s = try? JSONDecoder().decode(Settings.self, from: data) else { return }
        settings = s
    }

    func saveSettings() {
        let url = URL(fileURLWithPath: settingsPath)
        let encoder = JSONEncoder()
        encoder.outputFormatting = .prettyPrinted
        guard let data = try? encoder.encode(settings) else { return }
        try? data.write(to: url)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        loadSettings()

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        let iconPath = (baseDir as NSString).appendingPathComponent("MenuBarIcon.png")
        if let icon = NSImage(contentsOfFile: iconPath) {
            icon.isTemplate = true
            icon.size = NSSize(width: 18, height: 18)
            statusItem.button?.image = icon
        } else {
            statusItem.button?.title = "🫠"
        }

        let menu = NSMenu()

        toggleItem = NSMenuItem(title: "Start Tracking", action: #selector(toggleTracking), keyEquivalent: "")
        toggleItem.target = self
        menu.addItem(toggleItem)

        statusLabel = NSMenuItem(title: "Status: Stopped", action: nil, keyEquivalent: "")
        statusLabel.isEnabled = false
        menu.addItem(statusLabel)

        menu.addItem(NSMenuItem.separator())

        // ── Sensitivity submenu ─────────────────────────────────────────
        let sensItem = NSMenuItem(title: "Sensitivity", action: nil, keyEquivalent: "")
        let sensMenu = NSMenu()
        for val in [3, 5, 8, 10, 12, 15, 20, 25, 30] {
            let item = NSMenuItem(title: "\(val)", action: #selector(setSensitivity(_:)), keyEquivalent: "")
            item.target = self
            item.tag = val
            if Double(val) == settings.sensitivity { item.state = .on }
            sensMenu.addItem(item)
            sensItems.append(item)
        }
        sensItem.submenu = sensMenu
        menu.addItem(sensItem)

        // ── Dead Zone submenu ───────────────────────────────────────────
        let dzItem = NSMenuItem(title: "Dead Zone", action: nil, keyEquivalent: "")
        let dzMenu = NSMenu()
        let dzValues: [(String, Int)] = [
            ("0.010 — Very Tight", 10),
            ("0.020 — Tight", 20),
            ("0.030 — Snug", 30),
            ("0.040 — Normal", 40),
            ("0.050 — Relaxed", 50),
            ("0.060 — Wide", 60),
            ("0.080 — Very Wide", 80),
            ("0.100 — Max", 100),
        ]
        for (label, tag) in dzValues {
            let item = NSMenuItem(title: label, action: #selector(setDeadzone(_:)), keyEquivalent: "")
            item.target = self
            item.tag = tag
            let dzVal = Double(tag) / 1000.0
            if abs(dzVal - settings.deadzone) < 0.001 { item.state = .on }
            dzMenu.addItem(item)
            dzItems.append(item)
        }
        dzItem.submenu = dzMenu
        menu.addItem(dzItem)

        // ── Camera submenu ──────────────────────────────────────────────
        let camItem = NSMenuItem(title: "Camera", action: nil, keyEquivalent: "")
        let camMenu = NSMenu()
        for i in 0...3 {
            let item = NSMenuItem(title: "Camera \(i)", action: #selector(setCam(_:)), keyEquivalent: "")
            item.target = self
            item.tag = i
            if i == settings.cam { item.state = .on }
            camMenu.addItem(item)
        }
        camItem.submenu = camMenu
        menu.addItem(camItem)

        menu.addItem(NSMenuItem.separator())

        previewItem = NSMenuItem(title: "Show Camera Preview", action: #selector(togglePreview), keyEquivalent: "")
        previewItem.target = self
        menu.addItem(previewItem)

        let recalItem = NSMenuItem(title: "Recalibrate", action: #selector(recalibrate), keyEquivalent: "")
        recalItem.target = self
        menu.addItem(recalItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit HeadScroller", action: #selector(quitApp), keyEquivalent: "")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu

        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.updateStatus()
        }
    }

    // ── Tracking ────────────────────────────────────────────────────────
    @objc func toggleTracking() {
        if isTracking { stopTracking() } else { startTracking() }
    }

    func postScroll(_ amount: Int32) {
        guard let event = CGEvent(
            scrollWheelEvent2Source: nil,
            units: .line,
            wheelCount: 1,
            wheel1: amount,
            wheel2: 0,
            wheel3: 0
        ) else { return }
        event.post(tap: .cghidEventTap)
    }

    func startTracking() {
        loadSettings()

        let proc = Process()
        let binaryPath = (baseDir as NSString).appendingPathComponent("headscroller")
        proc.executableURL = URL(fileURLWithPath: binaryPath)

        var args = [
            "--cam", String(settings.cam),
            "--sensitivity", String(settings.sensitivity),
            "--deadzone", String(settings.deadzone),
            "--pipe-scroll",
        ]
        if !showingPreview {
            args.append("--no-window")
        }

        proc.arguments = args

        let pipe = Pipe()
        proc.standardOutput = pipe
        FileManager.default.createFile(atPath: logPath, contents: nil)
        let logHandle = FileHandle(forWritingAtPath: logPath)
        proc.standardError = logHandle ?? FileHandle.nullDevice

        // Read scroll commands and post CGEvents
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let str = String(data: data, encoding: .utf8) else { return }
            for line in str.split(separator: "\n") {
                if line.hasPrefix("SCROLL:"),
                   let val = Int32(line.dropFirst(7)) {
                    self?.postScroll(val)
                }
            }
        }

        do {
            try proc.run()
            process = proc
            isTracking = true
            toggleItem.title = "Stop Tracking"
            statusLabel.title = "Status: Tracking"
        } catch {
            statusLabel.title = "Status: Error launching"
        }
    }

    func stopTracking() {
        process?.terminate()
        process = nil
        isTracking = false
        toggleItem.title = "Start Tracking"
        statusLabel.title = "Status: Stopped"
    }

    @objc func togglePreview() {
        showingPreview = !showingPreview
        previewItem.title = showingPreview ? "Hide Camera Preview" : "Show Camera Preview"
        previewItem.state = showingPreview ? .on : .off
        // Restart to apply
        if isTracking {
            stopTracking()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.startTracking() }
        }
    }

    // ── Settings controls (save to file, Python hot-reloads) ──────────
    @objc func setSensitivity(_ sender: NSMenuItem) {
        settings.sensitivity = Double(sender.tag)
        saveSettings()
        for item in sensItems { item.state = .off }
        sender.state = .on
    }

    @objc func setDeadzone(_ sender: NSMenuItem) {
        settings.deadzone = Double(sender.tag) / 1000.0
        saveSettings()
        for item in dzItems { item.state = .off }
        sender.state = .on
    }

    @objc func setCam(_ sender: NSMenuItem) {
        settings.cam = sender.tag
        saveSettings()
        if let camMenu = sender.menu {
            for item in camMenu.items { item.state = .off }
        }
        sender.state = .on
        // Camera change requires restart
        if isTracking {
            stopTracking()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.startTracking() }
        }
    }

    @objc func recalibrate() {
        if isTracking {
            stopTracking()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.startTracking() }
        }
    }

    func updateStatus() {
        if isTracking, let proc = process, !proc.isRunning {
            isTracking = false
            toggleItem.title = "Start Tracking"
            statusLabel.title = "Status: Crashed — restart"
        }
    }

    @objc func quitApp() {
        stopTracking()
        NSApplication.shared.terminate(self)
    }
}

// ── Main ────────────────────────────────────────────────────────────────────
// Kill any other running instances to prevent duplicates
let myPid = ProcessInfo.processInfo.processIdentifier
let task = Process()
task.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep")
task.arguments = ["-f", "HeadScrollerMenuBar"]
let pgrepPipe = Pipe()
task.standardOutput = pgrepPipe
try? task.run()
task.waitUntilExit()
if let output = String(data: pgrepPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) {
    for line in output.split(separator: "\n") {
        if let pid = Int32(line.trimmingCharacters(in: .whitespaces)), pid != myPid {
            kill(pid, SIGTERM)
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
