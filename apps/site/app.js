// JavaScript deliberadamente mínimo: mejora la navegación sin recolectar datos.
document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', () => {
    // No se registra la interacción; el navegador maneja el ancla nativamente.
  });
});
