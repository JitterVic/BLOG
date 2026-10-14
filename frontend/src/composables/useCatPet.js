import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  isCatSoundEnabled,
  playBongoTap,
  playCuteMeow,
  playEureka,
  playPop,
  playPurr,
  playRocketLaunch,
  toggleCatSound,
} from "../lib/catAudio";

const STORAGE_KEY_POS = "blog_cat_pet_pos_v2";
// 猫咪热区（用于把坐标钳制在视口内），与 CatPet.vue 中 .cat-pet-widget 的尺寸保持一致
const PET_SIZE = 100;

// options.shouldIgnoreKey：焦点在某个控件内时（如猫咪本体），
// 让控件自己处理键位，避免全局 Bongo 反应覆盖它设置的状态。
export function useCatPet({ shouldIgnoreKey } = {}) {
  const route = useRoute();

  // 状态枚举：idle | stretch | groom | eureka | lookMouse | pounce | typing | dragging | petting | sleeping | launching
  const petState = ref("idle");
  const isHovered = ref(false);
  const isDragging = ref(false);
  const isSoundOn = ref(isCatSoundEnabled());
  const scrollProgress = ref(0);
  const scrollY = ref(0);
  const isVisible = ref(true);

  // 视线注视坐标 (Normalized -1 to 1)
  const gazeX = ref(0);
  const gazeY = ref(0);

  // 拖拽与坐标 (相对于视口 bottom/right 的偏移，或者基于像素坐标)
  const petPosition = ref({ x: 0, y: 0 }); // offset from initial corner or custom xy

  // 计时器句柄
  let idleTimer = null;
  let sleepTimer = null;
  let actionTimeout = null;
  let typingTimeout = null;
  let lastActivityTime = Date.now();
  let bongoToggle = false;

  const currentRouteName = computed(() => {
    const name = route.name;
    if (name === "home") return "home";
    if (name === "post") return "post";
    if (name === "posts") return "posts";
    if (name === "about") return "about";
    if (name === "not-found") return "not-found";
    return "default";
  });

  // 互动：被揪起来（点击已改为回顶部，这里保留状态供拖拽与唤醒复用）
  function handlePetClick() {
    if (isDragging.value || petState.value === "launching") return;

    resetInactivity();
    if (petState.value === "sleeping") {
      // 唤醒
      petState.value = "idle";
      playCuteMeow();
      return;
    }

    petState.value = "petting";
    playCuteMeow();
    playPop(620);
    playPurr();

    if (actionTimeout) clearTimeout(actionTimeout);
    actionTimeout = setTimeout(() => {
      if (petState.value === "petting") {
        petState.value = "idle";
      }
    }, 2800);
  }

  // 触发随机动作
  function triggerRandomAction() {
    if (
      isDragging.value ||
      petState.value === "typing" ||
      petState.value === "petting" ||
      petState.value === "launching" ||
      petState.value === "sleeping"
    ) {
      return;
    }

    const actions = ["stretch", "groom", "eureka", "lookMouse", "pounce"];
    const chosen = actions[Math.floor(Math.random() * actions.length)];

    petState.value = chosen;

    if (chosen === "eureka") {
      playEureka();
    } else if (chosen === "groom") {
      playPurr();
    } else if (chosen === "stretch") {
      playPurr();
    }

    const duration = chosen === "stretch" ? 3200 : chosen === "groom" ? 3600 : 2500;

    if (actionTimeout) clearTimeout(actionTimeout);
    actionTimeout = setTimeout(() => {
      if (petState.value === chosen) {
        petState.value = "idle";
      }
    }, duration);
  }

  // 键盘打字联动 (Bongo Cat Mode)
  function handleGlobalKeyDown(e) {
    // 忽略特定修饰键
    if (["Shift", "Control", "Alt", "Meta", "Escape"].includes(e.key)) return;
    if (shouldIgnoreKey?.(e)) return;

    resetInactivity();

    if (petState.value === "sleeping") {
      petState.value = "idle";
    }

    if (petState.value !== "launching" && !isDragging.value) {
      petState.value = "typing";
      bongoToggle = !bongoToggle;
      playBongoTap(bongoToggle);

      if (typingTimeout) clearTimeout(typingTimeout);
      typingTimeout = setTimeout(() => {
        if (petState.value === "typing") {
          petState.value = "idle";
        }
      }, 700);
    }
  }

  // 飞升回到顶部
  function launchToTop() {
    if (petState.value === "launching") return;

    // 点击算作活动：否则睡着的猫被点醒后会立刻再次入睡
    resetInactivity();
    if (actionTimeout) clearTimeout(actionTimeout);
    petState.value = "launching";
    playRocketLaunch();

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });

    setTimeout(() => {
      petState.value = "idle";
    }, 1200);
  }

  // 声音开关切换
  function toggleSound() {
    isSoundOn.value = toggleCatSound();
  }

  // 闲置重置
  function resetInactivity() {
    lastActivityTime = Date.now();
    if (petState.value === "sleeping") {
      petState.value = "idle";
    }
  }

  // 全局鼠标跟踪
  function handlePointerMove(e) {
    resetInactivity();

    // 计算鼠标与小猫相对视线
    const petEl = document.querySelector(".cat-pet-widget");
    if (petEl) {
      const rect = petEl.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const dx = e.clientX - centerX;
      const dy = e.clientY - centerY;

      // 归一化限制在 -1 ~ 1
      gazeX.value = Math.max(-1, Math.min(1, dx / Math.max(window.innerWidth * 0.4, 200)));
      gazeY.value = Math.max(-1, Math.min(1, dy / Math.max(window.innerHeight * 0.4, 200)));
    }
  }

  // 页面滚动监听
  function handleScroll() {
    const y = window.scrollY || 0;
    scrollY.value = y;
    const doc = document.documentElement;
    const maxScroll = Math.max(doc.scrollHeight - window.innerHeight, 1);
    scrollProgress.value = Math.min(Math.max(y / maxScroll, 0), 1);
  }

  // 定时器轮询循环（随机动作 & 休眠判定）
  function setupTimers() {
    // 随机动作调度：每 18~35 秒摇号
    function scheduleNextRandom() {
      const delay = Math.floor(Math.random() * 17000) + 18000;
      idleTimer = setTimeout(() => {
        if (petState.value === "idle" && Date.now() - lastActivityTime < 50000) {
          triggerRandomAction();
        }
        scheduleNextRandom();
      }, delay);
    }
    scheduleNextRandom();

    // 深度休眠检查：60 秒无操作入睡
    sleepTimer = setInterval(() => {
      if (
        petState.value === "idle" &&
        Date.now() - lastActivityTime >= 55000 &&
        !isDragging.value
      ) {
        petState.value = "sleeping";
        playPurr();
      }
    }, 5000);
  }

  // 视口内的坐标钳制（拖拽与历史位置恢复共用，把猫咪限制在右侧可拖拽区内）
  // x 保持"相对右下角的偏移"语义（负值向左），因此下界既要落回视口内，
  // 也要不小于 -PET_SIZE —— 否则拖到最左后窗口变窄，整只猫会停在屏幕外，
  // 而气泡里的"复位"入口已随文字功能移除，此时无法找回。
  function clampToViewport(x, y) {
    const maxLeftOffset = -(window.innerWidth - PET_SIZE - 20);
    const maxTopOffset = -(window.innerHeight - PET_SIZE - 20);
    const minLeftOffset = Math.max(maxLeftOffset, -PET_SIZE);
    return {
      x: Math.min(20, Math.max(minLeftOffset, x)),
      y: Math.min(20, Math.max(maxTopOffset, y)),
    };
  }

  // 位置持久化
  function loadSavedPosition() {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY_POS);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          petPosition.value = clampToViewport(parsed.x, parsed.y);
        }
      }
    } catch {}
  }

  function savePosition(x, y) {
    petPosition.value = { x, y };
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY_POS, JSON.stringify({ x, y }));
      } catch {}
    }
  }

  // 窗口尺寸变化后重新钳制，避免猫咪停在视口外（气泡的"复位"入口已移除，此时无法找回）
  function handleViewportResize() {
    const next = clampToViewport(petPosition.value.x, petPosition.value.y);
    if (next.x !== petPosition.value.x || next.y !== petPosition.value.y) {
      petPosition.value = next;
    }
  }

  // 监听路由改变：只让猫咪起身回到待机，不主动弹出文字
  watch(
    () => route.path,
    () => {
      petState.value = "idle";
      resetInactivity();
    }
  );

  onMounted(() => {
    loadSavedPosition();
    handleScroll();
    setupTimers();

    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("keydown", handleGlobalKeyDown, { passive: true });
    window.addEventListener("resize", handleViewportResize, { passive: true });
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", handleScroll);
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("keydown", handleGlobalKeyDown);
    window.removeEventListener("resize", handleViewportResize);
    if (idleTimer) clearTimeout(idleTimer);
    if (sleepTimer) clearInterval(sleepTimer);
    if (actionTimeout) clearTimeout(actionTimeout);
    if (typingTimeout) clearTimeout(typingTimeout);
  });

  return {
    petState,
    isHovered,
    isDragging,
    isSoundOn,
    scrollProgress,
    scrollY,
    isVisible,
    gazeX,
    gazeY,
    petPosition,
    currentRouteName,
    clampToViewport,
    handlePetClick,
    triggerRandomAction,
    launchToTop,
    toggleSound,
    savePosition,
  };
}
