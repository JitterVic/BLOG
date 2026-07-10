export const GO_TOP_EVENT = "zhizhi:go-top";

export function dispatchGoTopEvent() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new CustomEvent(GO_TOP_EVENT));
}
