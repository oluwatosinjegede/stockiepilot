(function () {
  
  const installBtn = document.getElementById("install-app-btn");
  const installHelp = document.getElementById("install-app-help");

  if (!installBtn) {
    return;
  }

  let deferredPrompt = null;
  const iosStoreUrl = installBtn.dataset.iosUrl || "https://apps.apple.com/";
  const androidStoreUrl = installBtn.dataset.androidUrl || "https://play.google.com/store";

  const ua = navigator.userAgent || "";
  const isIos = /iPhone|iPad|iPod/i.test(ua);
  const isAndroid = /Android/i.test(ua);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

  function setHelpMessage(message) {
    if (installHelp) {
      installHelp.textContent = message;
    }
  }

  function showInstallButton(label) {
    installBtn.classList.remove("hidden");
    installBtn.textContent = label;
  }

  function openStoreFallback() {
    const storeUrl = isIos ? iosStoreUrl : androidStoreUrl;
    window.open(storeUrl, "_blank", "noopener");
  }

  if (isStandalone) {
    installBtn.classList.add("hidden");
    setHelpMessage("StockiePilot is already installed on this device.");
    return;
  }

  showInstallButton("⬇ Install app");

  if (isIos) {
    setHelpMessage("On iPhone/iPad: tap Share, then choose 'Add to Home Screen' to install StockiePilot.");
  } else if (isAndroid) {
    setHelpMessage("On Android: tap install, or use browser menu > 'Install app' to add StockiePilot.");
  } else {
    setHelpMessage("Install StockiePilot for a full-screen POS experience. If prompt does not appear, use browser install menu.");
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    showInstallButton("⬇ Install app");
    setHelpMessage("Tap install to add StockiePilot on this device.");
  });

  installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) {
      openStoreFallback();
      setHelpMessage("No install prompt available in this browser. We opened the official app store link.");
      return;
    }

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;

    if (outcome === "accepted") {
      setHelpMessage("App installed. Launch StockiePilot from your home screen or desktop app launcher.");
    } else {
      setHelpMessage("Install was dismissed. You can install later from your browser menu.");
    }

    deferredPrompt = null;
    installBtn.classList.add("hidden");
  });

  window.addEventListener("appinstalled", () => {
    setHelpMessage("StockiePilot is installed on this device.");
    installBtn.classList.add("hidden");
  });
})();
