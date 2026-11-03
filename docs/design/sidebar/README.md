# Thiết kế lại Sidebar EduRAG

Nguồn thiết kế (Claude Design): `Main.dc.html` (mở rộng, 288×900), `Rail.dc.html` (thu gọn, 72×900), `canvas.json` (bố cục canvas).
Hai file `.dc.html` là mã nguồn HTML/CSS tĩnh, đọc trực tiếp để lấy kích thước, khoảng cách, màu. Không cần chạy; phần `<script type="text/x-dc">` chỉ mô phỏng trạng thái (gập nhóm, chọn dòng).

## Yêu cầu cho Claude Code
Viết lại `frontend/src/components/sidebar/Sidebar.tsx` (và chỉnh `ConversationHistory.tsx` nếu cần) theo thiết kế này.
- Giữ nguyên logic: `newChat`, `logoutRequest`, `useAuthStore`, `useChatStore`, `NavLink`, vai trò admin.
- Chỉ đổi giao diện. Dùng Tailwind (đã có) và `@phosphor-icons/react` thay cho SVG inline (ánh xạ icon ở bên dưới).
- Thêm trạng thái thu gọn (rail 72px), lưu vào `localStorage` (bọc try/catch).
- Chạy `npm run build` trong `frontend` để kiểm tra kiểu.

## Token
| Mục | Giá trị |
|---|---|
| Nền sidebar | `#0b1329`, viền phải `rgba(148,163,184,.14)` |
| Font | Plus Jakarta Sans; giờ dùng JetBrains Mono 11px |
| Xanh thương hiệu | `#10b981` (hover `#34d399`), chữ trên nền xanh `#04261b` |
| Chữ chính / phụ / mờ | `#ffffff` / `#c3cddb` / `#8d9bb0` |
| Nav thường | chữ `#aab6c8`, hover nền `rgba(148,163,184,.10)` |
| Nav đang chọn | nền `rgba(16,185,129,.15)`, chữ `#6ee7b7` |
| Dòng chat đang chọn | nền `rgba(148,163,184,.16)`, chữ trắng, đậm 600 |
| Nguy hiểm (đăng xuất) | hover nền `rgba(244,63,94,.16)`, chữ `#fda4af` |
| Focus | outline 2px `#34d399`, offset 2px |
| Bo góc | nút/nav/dòng 10–12px, avatar 12px |

## Bố cục bản mở rộng (rộng 288, padding 16/14/14)
1. **Header** cao 44: logo vuông 36px nền xanh (icon mũ tốt nghiệp), chữ "EduRAG" 18px/800 + chip "AI", dòng phụ "Trợ lý học vụ" 12px; nút icon 36px bên phải để thu gọn.
2. **Nút "Đoạn chat mới"** cao 42, nền xanh đặc, chữ tối 14px/700, icon Plus. Bỏ gradient và hiệu ứng phát sáng.
3. **Nav** (cách 14px, khoảng cách 2px, mỗi mục cao 40, icon 18px, chữ 14px/600):
   - Trang chat (`/chat`)
   - Thư viện tài liệu (`/library`) + badge số tài liệu active
   - Quản trị hệ thống (`/admin`), chỉ hiện khi `role === "admin"`
   Bỏ khối "Thư viện tài liệu" lớn và `Folder3DIcon`.
4. Đường kẻ ngăn, rồi **ô tìm kiếm** cao 38 (nền `rgba(148,163,184,.08)`, viền `rgba(148,163,184,.14)`, focus viền `#34d399`).
5. **Lịch sử hội thoại** (cuộn, `flex:1; min-height:0`): tiêu đề nhóm cao 32, chữ 11px/700 viết hoa giãn chữ, chevron xoay -90° khi gập, số đếm bên phải. Dòng chat cao 38, tiêu đề cắt `ellipsis`, giờ ở bên phải.
6. **Chân** (viền trên, padding-top 12): avatar 38 + chấm trạng thái, tên 13px/700, dòng phụ 12px; hai nút icon 36px: Cài đặt (`/settings`) và Đăng xuất. Thay cho ba dòng chữ trước đây.

## Bản thu gọn (rộng 72, căn giữa)
Logo 40 (bấm để mở rộng) → nút "Đoạn chat mới" 44 nền xanh → đường kẻ 32px → Trang chat / Thư viện / Quản trị / Lịch sử (nút 44, tooltip `title` + `aria-label`) → khoảng trống → Cài đặt, Đăng xuất, avatar 40 + chấm trạng thái.

## Ánh xạ icon (Phosphor)
mũ tốt nghiệp `GraduationCap`, thêm `Plus`, chat `ChatCircle`, thư viện `FolderSimple`, quản trị `ShieldCheck`, tìm `MagnifyingGlass`, chevron `CaretDown`, thu gọn `SidebarSimple`, lịch sử `ClockCounterClockwise`, cài đặt `SlidersHorizontal`, đăng xuất `SignOut`.

## Trợ năng
Icon-only phải có `aria-label`; mục đang chọn dùng `aria-current="page"`; nút gập nhóm có `aria-expanded`; mọi tương phản chữ ≥ 4.5:1.

## Lưu ý
Tiêu đề chat trong thiết kế chỉ là dữ liệu mẫu; dùng dữ liệu thật từ `ConversationHistory`. Số "4" ở badge thư viện lấy từ số tài liệu active thực tế.
