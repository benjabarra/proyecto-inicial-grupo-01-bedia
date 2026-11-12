// carrusel de fotos de la portada: cambia cada 6 segundos con un fundido suave.
// sin elegir nada pasan todas; al abrir una universidad, solo las suyas; al elegir campus, solo las de ese campus
(function () {
  var arte = document.querySelector(".portada-arte"), datos = document.getElementById("d-fotos");
  if (!arte || !datos || getComputedStyle(arte).display === "none") return;
  var fotos = JSON.parse(datos.textContent), capas = arte.querySelectorAll(".pa-foto"), lugar = arte.querySelector(".pa-lugar");
  var actual = 0, filtro = { uni: "", campus: "" }, cola = [], reloj = null, ultima = capas[0].getAttribute("src");
  function elegibles() {
    var l = fotos.filter(function (f) { return (!filtro.uni || f.uni === filtro.uni) && (!filtro.campus || f.campus === filtro.campus); });
    return l.length ? l : fotos;
  }
  function mezclar(l) {
    l = l.slice();
    for (var i = l.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = l[i]; l[i] = l[j]; l[j] = t; }
    return l;
  }
  function mostrar(f) {
    if (!f || f.src === ultima) return;
    var pre = new Image();
    pre.onload = function () {
      var nueva = capas[1 - actual], vieja = capas[actual];
      nueva.src = f.src; nueva.classList.remove("on"); void nueva.offsetWidth; nueva.classList.add("on");
      vieja.classList.remove("on");
      actual = 1 - actual; ultima = f.src;
      lugar.textContent = f.lugar;
    };
    pre.src = f.src;
  }
  function siguiente() {
    if (!cola.length) cola = mezclar(elegibles().filter(function (f) { return f.src !== ultima; }));
    mostrar(cola.shift());
  }
  function partir() { clearInterval(reloj); reloj = setInterval(function () { if (!document.hidden) siguiente(); }, 6000); }
  // al cambiar el filtro se muestra al tiro la foto principal (la primera de la lista)
  function filtrar(uni, campus) {
    filtro = { uni: uni, campus: campus }; cola = [];
    var l = elegibles(); if (l[0].src !== ultima) mostrar(l[0]); else siguiente();
    partir();
  }
  document.querySelectorAll("[data-uni]").forEach(function (caja) {
    caja.querySelector(".uni-cab").addEventListener("click", function () {
      var abierta = caja.classList.contains("abierta");
      var marcado = caja.querySelector('input[name="campus"]:checked');
      filtrar(abierta ? caja.getAttribute("data-uni") : "", abierta && marcado ? marcado.getAttribute("data-campus") : "");
    });
    caja.querySelectorAll('input[name="campus"]').forEach(function (r) {
      r.addEventListener("change", function () { filtrar(caja.getAttribute("data-uni"), r.getAttribute("data-campus")); });
    });
  });
  // precarga suave de las demas fotos cuando la pagina ya esta quieta
  setTimeout(function () { fotos.forEach(function (f) { var i = new Image(); i.src = f.src; }); }, 2500);
  partir();
})();
