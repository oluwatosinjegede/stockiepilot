(function () {
  const installBtn = document.getElementById("install-app-btn");
  const installHelp = document.getElementById("install-app-help");
  const installBanner = document.getElementById("install-app-banner");

  if (!installBtn) return;

  const ua = navigator.userAgent || "";
  const isIos = /iPhone|iPad|iPod/i.test(ua);
  const isAndroid = /Android/i.test(ua);

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  let deferredPrompt = null;

  function hideBannerAfterInstallClick() {
    if (!installBanner) return;
    installBanner.classList.add("hidden");
    localStorage.setItem("installNoticeClicked", "true");
  }


  // =========================
  // HELPERS
  // =========================
  function setHelpMessage(message) {
    if (installHelp) installHelp.textContent = message;
  }

  function showInstallButton(label = "Install App", animate = true) {
    installBtn.classList.remove("hidden");
    installBtn.textContent = label;

    if (animate && !localStorage.getItem("installPromptSeen")) {
      installBtn.classList.add("animate-pulse");
    }
  }

  function hideInstallButton() {
    installBtn.classList.add("hidden");
    installBtn.classList.remove("animate-pulse");
  }

  function stopAnimation() {
    installBtn.classList.remove("animate-pulse");
    localStorage.setItem("installPromptSeen", "true");
  }

  // =========================
  // ALREADY INSTALLED
  // =========================
  if (isStandalone) {
    if (installBanner) {
      installBanner.classList.add("hidden");
    } else {
      hideInstallButton();
      setHelpMessage("StockiePilot is already installed on this device.");
    }
    return;
  }

  if (localStorage.getItem("installNoticeClicked") === "true" && installBanner) {
    installBanner.classList.add("hidden");
    return;
  }

  // =========================
  // iOS (MANUAL INSTALL)
  // =========================
  if (isIos) {
    showInstallButton("How to Install");

    setHelpMessage(
      "Tap Share (⬆) in Safari, then select 'Add to Home Screen'."
    );

    installBtn.addEventListener("click", () => {
      stopAnimation();
      hideBannerAfterInstallClick();
      setHelpMessage(
        "Safari → Share (⬆) → 'Add to Home Screen' → Install."
      );
    });

    return;
  }

  // =========================
  // DEFAULT STATE
  // =========================
  hideInstallButton();
  setHelpMessage("Preparing install option...");

  // =========================
  // INSTALL PROMPT AVAILABLE
  // =========================
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;

    showInstallButton("⬇ Install App");

    if (isAndroid) {
      setHelpMessage("Tap install to add StockiePilot to your home screen.");
    } else {
      setHelpMessage("Install StockiePilot as a desktop app.");
    }
  });

  window.addEventListener("load", () => {
    window.setTimeout(() => {
      if (!deferredPrompt && !isIos) {
        showInstallButton("Install App", false);
        setHelpMessage("Use your browser menu (⋮) and choose 'Install App'.");
      }
    }, 1500);
  });

  // =========================
  // BUTTON CLICK
  // =========================
  installBtn.addEventListener("click", async () => {
    stopAnimation();
    hideBannerAfterInstallClick();

    if (!deferredPrompt) {
      setHelpMessage(
        "Install not ready. Use browser menu → 'Install App'."
      );
      return;
    }

    deferredPrompt.prompt();

    try {
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === "accepted") {
        setHelpMessage(
          "Installed successfully. Launch from your home screen."
        );
        hideInstallButton();
      } else {
        setHelpMessage(
          "Install cancelled. You can install anytime from the browser menu."
        );
      }
    } catch (error) {
      setHelpMessage("Installation failed. Please try again.");
    }

    deferredPrompt = null;
  });

  // =========================
  // INSTALLED EVENT
  // =========================
  window.addEventListener("appinstalled", () => {
    stopAnimation();
    localStorage.removeItem("installNoticeClicked");
    setHelpMessage("StockiePilot is now installed.");
    hideInstallButton();
  });
})();