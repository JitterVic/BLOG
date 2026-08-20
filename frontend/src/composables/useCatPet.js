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
import {
  getPageGreeting,
  getRandomFortune,
  PET_STATUS_TEXTS,
} from "../lib/catFortunes";

const STORAGE_KEY_POS = "blog_cat_pet_pos_v2";

export function useCatPet() {
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

  // 对话气泡
  const bubbleVisible = ref(false);
  const bubbleText = ref("");
  const bubbleTag = ref("闲聊");
  let bubbleTimer = null;

  // 拖拽与坐标 (相对于视口 bottom/right 的偏移，或者基于像素坐标)
  const petPosition = ref({ x: 0, y: 0 }); // offset from initial corner or custom xy
  const hasCustomPosition = ref(false);

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

  const statusText = computed(() => {
    return PET_STATUS_TEXTS[petState.value] || "伴读中";
  });

  // 弹出气泡
  function showBubble(text, tag = "陪伴", duration = 4000) {
    if (bubbleTimer) clearTimeout(bubbleTimer);
    bubbleText.value = text;
    bubbleTag.value = tag;
    bubbleVisible.value = true;
    if (duration > 0) {
      bubbleTimer = setTimeout(() => {
        bubbleVisible.value = false;
        bubbleTimer = null;
      }, duration);
    }
  }

  function hideBubble() {
    if (bubbleTimer) clearTimeout(bubbleTimer);
    bubbleVisible.value = false;
  }

  // 互动：抚摸 / 点击小猫
  function handlePetClick() {
    if (isDragging.value || petState.value === "launching") return;

    resetInactivity();
    if (petState.value === "sleeping") {
      // 唤醒
      petState.value = "idle";
      playCuteMeow();
      showBubble("喵呜？你回来啦～", "醒来", 3500);
      return;
    }

    petState.value = "petting";
    playCuteMeow();
    playPop(620);
    playPurr();

    const fortune = getRandomFortune();
    showBubble(fortune.text, fortune.tag, 4500);

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
      showBubble("灵光一闪！想到了一个精妙的解法 ✨", "灵感", 3000);
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

    if (actionTimeout) clearTimeout(actionTimeout);
    petState.value = "launching";
    playRocketLaunch();
    showBubble("火箭喷射！回到顶部 🚀", "回顶", 2000);

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
    if (isSoundOn.value) {
      showBubble("小猫音效已开启 🔔", "设置", 2000);
    } else {
      showBubble("已切换为静音模式 🔕", "设置", 2000);
    }
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
      const dist = Math.hypot(dx, dy) || 1;

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
        showBubble("好困呀... 先眯一小会儿 Zzz", "瞌睡", 3500);
      }
    }, 5000);
  }

  // 位置持久化
  function loadSavedPosition() {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY_POS);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          petPosition.value = parsed;
          hasCustomPosition.value = true;
        }
      }
    } catch {}
  }

  function savePosition(x, y) {
    petPosition.value = { x, y };
    hasCustomPosition.value = true;
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY_POS, JSON.stringify({ x, y }));
      } catch {}
    }
  }

  function resetPosition() {
    petPosition.value = { x: 0, y: 0 };
    hasCustomPosition.value = false;
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY_POS);
    }
    showBubble("位置已重置回角落 📍", "提示", 2000);
  }

  // 监听路由改变，自动呈现页面专属问候
  watch(
    () => route.path,
    () => {
      petState.value = "idle";
      resetInactivity();
      setTimeout(() => {
        const greeting = getPageGreeting(currentRouteName.value);
        showBubble(greeting, "伴读", 3800);
      }, 500);
    }
  );

  onMounted(() => {
    loadSavedPosition();
    handleScroll();
    setupTimers();

    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("keydown", handleGlobalKeyDown, { passive: true });

    // 初次进入展示问候
    setTimeout(() => {
      const greeting = getPageGreeting(currentRouteName.value);
      showBubble(greeting, "你好", 4000);
    }, 1200);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", handleScroll);
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("keydown", handleGlobalKeyDown);
    if (idleTimer) clearTimeout(idleTimer);
    if (sleepTimer) clearInterval(sleepTimer);
    if (bubbleTimer) clearTimeout(bubbleTimer);
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
    bubbleVisible,
    bubbleText,
    bubbleTag,
    petPosition,
    hasCustomPosition,
    currentRouteName,
    statusText,
    showBubble,
    hideBubble,
    handlePetClick,
    triggerRandomAction,
    launchToTop,
    toggleSound,
    savePosition,
    resetPosition,
  };
}
