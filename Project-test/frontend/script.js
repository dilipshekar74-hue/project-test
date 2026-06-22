const clock = document.getElementById("clock");

function tick() {
  if (clock) {
    clock.textContent = new Date().toLocaleString();
  }
}

tick();
setInterval(tick, 1000);
const clock = document.getElementById("clock");

function tick() {
  if (clock) {
    clock.textContent = new Date().toLocaleString();
  }
}

tick();
setInterval(tick, 1000);
