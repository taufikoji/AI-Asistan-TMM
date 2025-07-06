document.addEventListener("DOMContentLoaded", () => {
  // Toggle tema gelap/terang
  const toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const theme = document.documentElement.getAttribute("data-theme");
      document.documentElement.setAttribute(
        "data-theme",
        theme === "dark" ? "light" : "dark"
      );
      localStorage.setItem("theme", theme === "dark" ? "light" : "dark");
    });
  }

  // Terapkan tema tersimpan
  const savedTheme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  // Tombol kembali ke landing
  const backBtn = document.querySelector(".back-to-landing");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      window.location.href = "/";
    });
  }
});