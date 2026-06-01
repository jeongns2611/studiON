import { onUnmounted } from 'vue';
import { useTrackStore } from '../store/useTrackStore';

export function useAutoScroll() {
  let scrollContainer: HTMLElement | null = null;
  let autoScrollRafId: number | null = null;
  
  let currentClientX = 0;
  let currentClientY = 0;

  const startAutoScroll = (
    clientX: number, 
    clientY: number, 
    onScroll: () => void, 
    options: { enableVertical?: boolean; edgeThreshold?: number; scrollSpeed?: number } = {}
  ) => {
    const { enableVertical = false, edgeThreshold = 80, scrollSpeed = 15 } = options;
    
    scrollContainer = document.querySelector('.custom-scrollbar') as HTMLElement;
    if (!scrollContainer) return;
    
    currentClientX = clientX;
    currentClientY = clientY;
    
    if (autoScrollRafId) cancelAnimationFrame(autoScrollRafId);
    
    const loop = () => {
      if (!scrollContainer) return;
      
      let scrolled = false;
      
      // 오른쪽 스크롤
      if (currentClientX > window.innerWidth - edgeThreshold) {
        scrollContainer.scrollLeft += scrollSpeed;
        scrolled = true;
      }
      
      // 왼쪽 스크롤 (왼쪽 패널 사이즈 224px 고려)
      const trackStore = useTrackStore();
      if (currentClientX < 224 * trackStore.workspaceZoom + edgeThreshold) {
        scrollContainer.scrollLeft -= scrollSpeed;
        scrolled = true;
      }
      
      // 세로 스크롤 허용 시
      if (enableVertical) {
        if (currentClientY > window.innerHeight - 200) {
          scrollContainer.scrollTop += scrollSpeed;
          scrolled = true;
        }
        if (currentClientY < 120 + edgeThreshold) {
          scrollContainer.scrollTop -= scrollSpeed;
          scrolled = true;
        }
      }
      
      if (scrolled) {
        onScroll();
      }
      
      autoScrollRafId = requestAnimationFrame(loop);
    };
    
    autoScrollRafId = requestAnimationFrame(loop);
  };
  
  const updatePointer = (clientX: number, clientY: number) => {
    currentClientX = clientX;
    currentClientY = clientY;
  };
  
  const stopAutoScroll = () => {
    if (autoScrollRafId) {
      cancelAnimationFrame(autoScrollRafId);
      autoScrollRafId = null;
    }
  };
  
  onUnmounted(() => {
    stopAutoScroll();
  });
  
  return {
    startAutoScroll,
    updatePointer,
    stopAutoScroll
  };
}
