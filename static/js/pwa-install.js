(function () {
  let deferredPrompt = null;

  const installBtn = document.getElementById("install-app-btn");
  const installHelp = document.getElementById("install-app-help");

  if (!installBtn) return;

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    installBtn.classList.remove("hidden");
    if (installHelp) {
      installHelp.textContent = "Tap install to add StockiePilot on this device.";
    }
  });

  installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) {
      if (installHelp) {
        installHelp.textContent = "If install does not appear, open browser menu and choose 'Install app' or 'Add to Home Screen'.";
      }
      return;
    }

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;

    if (installHelp) {
      installHelp.textContent =
        outcome === "accepted"
          ? "App installed. You can launch StockiePilot from your home screen or desktop app launcher."
          : "Install was dismissed. You can install later from your browser menu.";
    }

    deferredPrompt = null;
    installBtn.classList.add("hidden");
  });

  window.addEventListener("appinstalled", () => {
    if (installHelp) {
      installHelp.textContent = "StockiePilot is installed on this device.";
    }
    installBtn.classList.add("hidden");
  });
})();
