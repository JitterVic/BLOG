<script setup>
import { computed } from "vue";

// 静态导入 13 种高质量透明通道动作切图
import imgAboutWelcome from "../../assets/pet/about_welcome.png";
import imgArchiveLens from "../../assets/pet/archive_lens.png";
import imgCuriousLook from "../../assets/pet/curious_look.png";
import imgDraggingScruff from "../../assets/pet/dragging_scruff.png";
import imgEureka from "../../assets/pet/eureka.png";
import imgGrooming from "../../assets/pet/grooming.png";
import imgIdleHome from "../../assets/pet/idle_home.png";
import imgPettingHearts from "../../assets/pet/petting_hearts.png";
import imgReadingBook from "../../assets/pet/reading_book.png";
import imgRocketLaunch from "../../assets/pet/rocket_launch.png";
import imgSleepingCurl from "../../assets/pet/sleeping_curl.png";
import imgStretch from "../../assets/pet/stretch.png";
import imgTypingBongo from "../../assets/pet/typing_bongo.png";

const props = defineProps({
  state: {
    type: String,
    default: "idle", // idle | stretch | groom | eureka | lookMouse | pounce | typing | dragging | petting | sleeping | launching
  },
  route: {
    type: String,
    default: "home", // home | post | posts | about | not-found | default
  },
  gazeX: {
    type: Number,
    default: 0,
  },
  gazeY: {
    type: Number,
    default: 0,
  },
  isHovered: {
    type: Boolean,
    default: false,
  },
  isDragging: {
    type: Boolean,
    default: false,
  },
});

// 计算当前应呈现的图片切图资产
const currentSprite = computed(() => {
  // 1. 优先特殊即时互动状态
  if (props.state === "sleeping") return imgSleepingCurl;
  if (props.state === "dragging") return imgDraggingScruff;
  if (props.state === "typing") return imgTypingBongo;
  if (props.state === "stretch") return imgStretch;
  if (props.state === "groom") return imgGrooming;
  if (props.state === "eureka") return imgEureka;
  if (props.state === "petting") return imgPettingHearts;
  if (props.state === "lookMouse" || props.state === "pounce") return imgCuriousLook;
  if (props.state === "launching") return imgRocketLaunch;

  // 2. 页面专属待机姿态
  if (props.route === "post") return imgReadingBook;
  if (props.route === "posts") return imgArchiveLens;
  if (props.route === "about") return imgAboutWelcome;
  if (props.route === "not-found") return imgCuriousLook;

  // 3. 首页默认闲适喝茶姿态
  return imgIdleHome;
});

// 动态视线与姿态倾斜计算 (Micro-tilts)
const spriteTransform = computed(() => {
  if (props.state === "dragging") {
    return "scale(0.95)";
  }
  if (props.state === "sleeping" || props.state === "stretch") {
    return "none";
  }

  const tx = props.gazeX * 4.5;
  const ty = props.gazeY * 3;
  const rot = props.gazeX * 4;
  return `translate3d(${tx}px, ${ty}px, 0) rotate(${rot}deg)`;
});
</script>

<template>
  <div
    class="cat-avatar-frame"
    :class="[
      `state-${state}`,
      `route-${route}`,
      {
        'is-hovered': isHovered,
        'is-dragging': isDragging,
      },
    ]"
  >
    <!-- 地面动态阴影 -->
    <div class="cat-drop-shadow"></div>

    <!-- 主角色高精度切图层 -->
    <div class="sprite-stage" :style="{ transform: spriteTransform }">
      <img
        :src="currentSprite"
        :alt="`博客吉祥物猫咪桌宠 - ${state}`"
        class="cat-sprite-img"
        draggable="false"
      />

      <!-- 特效图层：首页咖啡热气微动 -->
      <div v-if="route === 'home' && state === 'idle'" class="fx-steam-wrap">
        <span class="steam-particle s1"></span>
        <span class="steam-particle s2"></span>
      </div>

      <!-- 特效图层：睡眠 Zzz 粒子 -->
      <div v-if="state === 'sleeping'" class="fx-zzz-wrap">
        <span class="zzz-p z1">Z</span>
        <span class="zzz-p z2">z</span>
        <span class="zzz-p z3">z</span>
      </div>

      <!-- 特效图层：灵光一闪发光光晕 -->
      <div v-if="state === 'eureka'" class="fx-eureka-glow">
        <span class="sparkle sp1">✦</span>
        <span class="sparkle sp2">✦</span>
      </div>

      <!-- 特效图层：打字代码火花 -->
      <div v-if="state === 'typing'" class="fx-typing-sparks">
        <span class="spark-key k1">⌨️</span>
        <span class="spark-key k2">✦</span>
      </div>

      <!-- 特效图层：抚摸爱心泡泡 -->
      <div v-if="state === 'petting'" class="fx-pet-hearts">
        <span class="heart-p h1">♥</span>
        <span class="heart-p h2">♥</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cat-avatar-frame {
  position: relative;
  width: 108px;
  height: 108px;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  pointer-events: none;
  transform-origin: 50% 90%;
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 1. 地面柔和阴影 */
.cat-drop-shadow {
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  width: 74px;
  height: 14px;
  background: radial-gradient(ellipse at center, rgba(38, 26, 15, 0.24) 0%, rgba(38, 26, 15, 0) 72%);
  border-radius: 50%;
  z-index: 1;
  transition: all 0.3s ease;
}

/* 2. 精灵切图舞台 */
.sprite-stage {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  transition: transform 0.12s cubic-bezier(0.2, 0.8, 0.4, 1);
}

.cat-sprite-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: drop-shadow(0 6px 14px rgba(35, 25, 15, 0.1));
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  transform-origin: 50% 88%;
}

/* ===================================================
   3. 动画与微表情系统
   =================================================== */

/* 呼吸闲置微动 */
.state-idle .cat-sprite-img {
  animation: petBreathe 3.4s ease-in-out infinite alternate;
}

@keyframes petBreathe {
  0% { transform: scale(1); }
  100% { transform: scale(1.025, 0.985) translateY(1px); }
}

/* 睡眠安详呼吸 */
.state-sleeping .cat-sprite-img {
  animation: sleepBreathe 3.6s ease-in-out infinite alternate;
}

@keyframes sleepBreathe {
  0% { transform: scale(1); }
  100% { transform: scale(1.03, 0.97) translateY(1.5px); }
}

.state-sleeping .cat-drop-shadow {
  width: 82px;
  opacity: 0.85;
}

/* 悬空拖拽摇摆 */
.state-dragging .cat-sprite-img {
  animation: scruffSwing 0.45s ease-in-out infinite alternate;
  transform-origin: 50% 12%;
}

@keyframes scruffSwing {
  0% { transform: rotate(-3.5deg) scale(0.95); }
  100% { transform: rotate(3.5deg) scale(0.95); }
}

.state-dragging .cat-drop-shadow {
  transform: translateX(-50%) translateY(12px) scale(0.6);
  opacity: 0.15;
}

/* Bongo 敲键盘快速交替震动 */
.state-typing .cat-sprite-img {
  animation: bongoVibrate 0.12s infinite alternate;
}

@keyframes bongoVibrate {
  0% { transform: translateY(0) scale(1); }
  100% { transform: translateY(-2px) scale(1.015, 0.985); }
}

/* 伸懒腰拉伸 */
.state-stretch .cat-sprite-img {
  animation: stretchAnim 2.2s ease-in-out infinite alternate;
}

@keyframes stretchAnim {
  0% { transform: scaleX(1); }
  100% { transform: scaleX(1.05) translateY(2px); }
}

/* 灵光一闪弹跳 */
.state-eureka .cat-sprite-img {
  animation: eurekaBounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) infinite alternate;
}

@keyframes eurekaBounce {
  0% { transform: translateY(0); }
  100% { transform: translateY(-5px); }
}

/* 悬停微浮 */
.is-hovered:not(.is-dragging) .cat-sprite-img {
  transform: translateY(-4px) scale(1.04);
}

/* ===================================================
   4. 粒子与特效层 (FX Layers)
   =================================================== */

/* 热气升腾 */
.fx-steam-wrap {
  position: absolute;
  bottom: 30px;
  right: 18px;
  display: flex;
  gap: 3px;
  pointer-events: none;
}

.steam-particle {
  width: 2px;
  height: 8px;
  background: rgba(180, 160, 140, 0.6);
  border-radius: 2px;
  animation: steamFloat 1.8s infinite ease-out;
}

.steam-particle.s2 { animation-delay: 0.9s; }

@keyframes steamFloat {
  0% { opacity: 0; transform: translateY(2px) scaleY(0.7); }
  50% { opacity: 0.8; }
  100% { opacity: 0; transform: translateY(-8px) scaleY(1.3); }
}

/* Zzz 睡眠气泡 */
.fx-zzz-wrap {
  position: absolute;
  top: 10px;
  right: 14px;
  display: flex;
  gap: 2px;
  font-family: monospace;
  font-weight: 900;
  color: var(--accent, #8b2500);
}

.zzz-p {
  display: inline-block;
  opacity: 0;
  animation: zzzRise 2.2s infinite ease-out;
}

.zzz-p.z1 { font-size: 14px; animation-delay: 0s; }
.zzz-p.z2 { font-size: 11px; animation-delay: 0.5s; }
.zzz-p.z3 { font-size: 9px; animation-delay: 1.0s; }

@keyframes zzzRise {
  0% { opacity: 0; transform: translateY(4px) scale(0.7); }
  45% { opacity: 1; transform: translateY(-5px) scale(1.1); }
  100% { opacity: 0; transform: translateY(-18px) scale(0.85); }
}

/* 灵光星星光晕 */
.fx-eureka-glow {
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 13px;
  color: #e8ad38;
}

.sparkle {
  position: absolute;
  animation: starSparkle 0.8s infinite alternate;
}

.sparkle.sp1 { left: -20px; top: 0; }
.sparkle.sp2 { right: -20px; top: -4px; animation-delay: 0.4s; }

@keyframes starSparkle {
  0% { opacity: 0.3; transform: scale(0.8) rotate(0deg); }
  100% { opacity: 1; transform: scale(1.3) rotate(30deg); }
}

/* 打字火花 */
.fx-typing-sparks {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  width: 80px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}

.spark-key {
  animation: keySpark 0.4s infinite alternate;
}

.spark-key.k2 {
  color: #e8ad38;
}

@keyframes keySpark {
  0% { opacity: 0.2; transform: translateY(0); }
  100% { opacity: 1; transform: translateY(-4px); }
}

/* 抚摸爱心 */
.fx-pet-hearts {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  width: 70px;
  display: flex;
  justify-content: space-between;
  color: #e11d48;
  font-size: 14px;
}

.heart-p {
  animation: heartFloat 1s infinite alternate ease-in-out;
}

.heart-p.h2 { animation-delay: 0.5s; }

@keyframes heartFloat {
  0% { transform: translateY(0) scale(0.85); }
  100% { transform: translateY(-6px) scale(1.25); }
}
</style>
