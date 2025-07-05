document.getElementById("toggle-theme").addEventListener("click", () => {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme");
  html.setAttribute("data-theme", current === "dark" ? "light" : "dark");
});

// Load particles
tsParticles.load("particles-js", {
  fullScreen: { enable: false },
  particles: {
    number: { value: 60 },
    color: { value: "#ffffff" },
    shape: { type: "circle" },
    opacity: { value: 0.4 },
    size: { value: { min: 1, max: 4 } },
    move: {
      enable: true,
      speed: 1,
      direction: "none",
      outModes: { default: "bounce" }
    }
  }
});
