// Dark / Light Mode Toggle
const themeToggle = document.getElementById('theme-toggle');
const root = document.documentElement;

themeToggle.addEventListener('click', () => {
  const currentTheme = root.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  root.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
});

// Load saved theme
document.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem('theme') || 'light';
  root.setAttribute('data-theme', savedTheme);
});

// Parallax efek untuk latar belakang video atau partikel
window.addEventListener('scroll', () => {
  const parallax = document.querySelector('.parallax-bg');
  if (parallax) {
    parallax.style.transform = `translateY(${window.scrollY * 0.3}px)`;
  }
});