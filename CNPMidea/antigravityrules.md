# Creative Frontend Tech Stack & Architecture Rules

Khi thiết kế giao diện cho dự án này, hãy luôn ưu tiên sử dụng hệ sinh thái thư viện đẳng cấp đã được cài đặt sẵn:

1. **Smooth Scroll (Lenis + GSAP):**
   - Luôn bọc ứng dụng bằng `Lenis` (`lenis/react` hoặc khởi tạo chuẩn) và đồng bộ trực tiếp với `gsap.ticker` cùng `ScrollTrigger.update`.
2. **Animation (GSAP & Motion):**
   - Dùng `GSAP` + `@gsap/react` (`useGSAP` hook) cho các hiệu ứng cuộn phức tạp (`ScrollTrigger`), ghim phần tử (pinning), và tách chữ.
   - Dùng `motion/react` (Framer Motion) cho hiệu ứng xuất hiện của UI, micro-interactions (hover, tap), và chuyển đổi layout (`layoutId`).
3. **3D & Interactive Media:**
   - Dùng `@react-three/fiber` và `@react-three/drei` khi cần tạo không gian 3D, hạt 3D hoặc shader.
   - Dùng `@splinetool/react-spline` khi nhúng mô hình Spline 3D.
   - Dùng `@rive-app/react-canvas` cho các icon/nhân vật tương tác vector.
4. **UI Components (Aceternity & Magic UI):**
   - Tạo file `lib/utils.ts` với hàm `cn()` chuẩn từ `clsx` và `tailwind-merge`.
   - Khi người dùng yêu cầu các thành phần như Bento Grid, Aurora Background, 3D Card, Border Beam, Marquee... hãy tự động chạy lệnh `npx shadcn@latest add` từ registry của Aceternity UI hoặc Magic UI, hoặc viết component theo đúng cấu trúc của chúng.
