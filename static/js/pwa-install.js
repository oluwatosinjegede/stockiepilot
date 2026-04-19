(function () {
  const installBtn = document.getElementById("install-app-btn");
  const installHelp = document.getElementById("install-app-help");

  if (!installBtn) return;

  const ua = navigator.userAgent || "";
  const isIos = /iPhone|iPad|iPod/i.test(ua);
  const isAndroid = /Android/i.test(ua);

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  let deferredPrompt = null;

  function setHelpMessage(message) {
    if (installHelp) installHelp.textContent = message;
  }

  function showInstallButton(label = "Install App", animate = true) {
    installBtn.classList.remove("hidden");
    installBtn.textContent = label;

    if (animate && !localStorage.getItem("installPromptSeen")) {
      installBtn.classList.add("animate-pulse", "install-shine");
    }
  }

  function hideInstallButton() {
    installBtn.classList.add("hidden");
    installBtn.classList.remove("animate-pulse", "install-shine");
  }

  function stopAnimation() {
    installBtn.classList.remove("animate-pulse", "install-shine");
    localStorage.setItem("installPromptSeen", "true");
  }

  if (isStandalone) {
    hideInstallButton();
    setHelpMessage("StockiePilot is already installed on this device.");
    return;
  }

  if (isIos) {
    showInstallButton("How to Install");

    setHelpMessage("On iPhone/iPad, open Safari, tap Share, then tap 'Add to Home Screen'.");

    installBtn.addEventListener("click", () => {
      stopAnimation();
      setHelpMessage("Safari → Share → Add to Home Screen.");
    });

    return;
  }

  hideInstallButton();
  setHelpMessage("Preparing install option...");

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;

    showInstallButton("⬇ Install App");

    if (isAndroid) {
      setHelpMessage("Tap install to add StockiePilot to your Android home screen.");
    } else {
      setHelpMessage("Install StockiePilot as a desktop app.");
    }
  });

  installBtn.addEventListener("click", async () => {
    stopAnimation();

    if (!deferredPrompt) {
      setHelpMessage("Install option is not ready yet. Use your browser menu and choose Install App.");
      return;
    }

    deferredPrompt.prompt();

    try {
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === "accepted") {
        setHelpMessage("Installed successfully. Open StockiePilot from your home screen or desktop.");
        hideInstallButton();
      } else {
        setHelpMessage("Install dismissed. You can install later from the browser menu.");
      }
    } catch (error) {
      setHelpMessage("Installation failed. Please try again.");
    }

    deferredPrompt = null;
  });

  window.addEventListener("appinstalled", () => {
    stopAnimation();
    setHelpMessage("StockiePilot is now installed.");
    hideInstallButton();
  });
})();