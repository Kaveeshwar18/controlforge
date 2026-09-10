// The scrolling element is .app-main, not the window. Calling
// element.scrollIntoView() from inside a click handler gets cancelled by the
// browser's own focus-scroll on the clicked button, so we compute the offset
// and drive the container directly instead.
export function scrollToSection(id) {
  const el = document.getElementById(id);
  const container = document.querySelector(".app-main");
  if (!el || !container) return;
  const top =
    el.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 8;
  // assigning scrollTop (rather than scrollTo({behavior:"smooth"})) is the
  // reliable path: the animation comes from `scroll-behavior: smooth` in CSS,
  // and where that isn't honoured it simply jumps instead of doing nothing.
  container.scrollTop = Math.max(0, top);
}
