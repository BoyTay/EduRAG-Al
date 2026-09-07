import { CheckCircle, Key, ShieldCheck, UserCircle } from "@phosphor-icons/react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { changeAccountPassword, updateAccountProfile } from "../services/api";
import { useAuthStore } from "../stores/authStore";
import { Button } from "../components/ui/Button";

const profileSchema = z.object({ display_name: z.string().trim().min(2, "Tên hiển thị cần ít nhất 2 ký tự").max(100) });
const passwordSchema = z.object({ current_password: z.string().min(1, "Hãy nhập mật khẩu hiện tại"), new_password: z.string().min(8, "Mật khẩu mới cần ít nhất 8 ký tự"), confirm_password: z.string() }).refine((data) => data.new_password === data.confirm_password, { path: ["confirm_password"], message: "Xác nhận mật khẩu chưa khớp" });
type ProfileForm = z.infer<typeof profileSchema>;
type PasswordForm = z.infer<typeof passwordSchema>;

function readError(error: unknown, fallback: string) {
  const response = error as { response?: { data?: { detail?: string } } };
  return response.response?.data?.detail || fallback;
}

export function Settings() {
  const user = useAuthStore((state) => state.user);
  const updateUser = useAuthStore((state) => state.updateUser);
  const profile = useForm<ProfileForm>({ resolver: zodResolver(profileSchema), defaultValues: { display_name: user?.display_name || "" } });
  const password = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  const saveProfile = async (values: ProfileForm) => {
    profile.clearErrors("root");
    try {
      const nextUser = await updateAccountProfile(values.display_name);
      updateUser(nextUser);
      profile.reset({ display_name: nextUser.display_name || "" });
      profile.setError("root", { message: "Đã lưu tên hiển thị." });
    } catch (error) { profile.setError("root", { message: readError(error, "Không thể cập nhật hồ sơ.") }); }
  };

  const savePassword = async (values: PasswordForm) => {
    password.clearErrors("root");
    try {
      await changeAccountPassword(values.current_password, values.new_password);
      password.reset();
      password.setError("root", { message: "Đã cập nhật mật khẩu." });
    } catch (error) { password.setError("root", { message: readError(error, "Không thể đổi mật khẩu.") }); }
  };

  const field = "mt-2 h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-green-100";
  return <section className="h-full overflow-y-auto px-5 py-7 md:px-8"><div className="mx-auto max-w-4xl"><div className="mb-8"><p className="text-xs font-bold tracking-[.14em] text-brand">TÀI KHOẢN</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">Cài đặt tài khoản</h1><p className="mt-2 text-sm text-muted">Quản lý thông tin hồ sơ và bảo mật đăng nhập.</p></div><div className="grid gap-5 lg:grid-cols-[.9fr_1.1fr]"><aside className="rounded-2xl border border-line bg-white p-6 shadow-[0_8px_24px_rgba(46,125,50,.06)]"><span className="grid size-14 place-items-center rounded-2xl bg-green-100 text-brand"><UserCircle size={32} weight="fill" /></span><h2 className="mt-4 text-lg font-semibold text-ink">{user?.display_name || "Tài khoản EduRAG"}</h2><p className="mt-1 break-all text-sm text-muted">{user?.email}</p><span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1.5 text-xs font-semibold text-brand"><ShieldCheck size={16} weight="fill" />{user?.role === "admin" ? "Quản trị viên" : "Sinh viên"}</span><p className="mt-6 border-t border-line pt-5 text-xs leading-5 text-muted">Tên đăng nhập không thể thay đổi tại đây để đảm bảo an toàn lịch sử hội thoại.</p></aside><div className="space-y-5"><form onSubmit={profile.handleSubmit(saveProfile)} className="rounded-2xl border border-line bg-white p-6 shadow-[0_8px_24px_rgba(46,125,50,.06)]"><h2 className="text-lg font-semibold text-ink">Hồ sơ cá nhân</h2><p className="mt-1 text-sm text-muted">Tên này sẽ xuất hiện trong thanh điều hướng.</p><label className="mt-5 block text-sm font-semibold text-ink">Tên hiển thị<input className={field} {...profile.register("display_name")} /></label>{profile.formState.errors.display_name && <p className="mt-1 text-xs text-error">{profile.formState.errors.display_name.message}</p>}<p className="mt-4 text-xs text-muted">Tên đăng nhập: {user?.email}</p>{profile.formState.errors.root && <p role="status" className={`mt-4 flex items-center gap-1.5 text-sm ${profile.formState.errors.root.message?.startsWith("Đã") ? "text-brand" : "text-error"}`}><CheckCircle size={16} />{profile.formState.errors.root.message}</p>}<Button type="submit" className="mt-5" disabled={profile.formState.isSubmitting}>{profile.formState.isSubmitting ? "Đang lưu..." : "Lưu thay đổi"}</Button></form><form onSubmit={password.handleSubmit(savePassword)} className="rounded-2xl border border-line bg-white p-6 shadow-[0_8px_24px_rgba(46,125,50,.06)]"><div className="flex items-start gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-green-100 text-brand"><Key size={21} weight="duotone" /></span><div><h2 className="text-lg font-semibold text-ink">Đổi mật khẩu</h2><p className="mt-1 text-sm text-muted">Dùng tối thiểu 8 ký tự để bảo vệ tài khoản.</p></div></div>{([['current_password', 'Mật khẩu hiện tại'], ['new_password', 'Mật khẩu mới'], ['confirm_password', 'Xác nhận mật khẩu mới']] as const).map(([name, label]) => <label key={name} className="mt-4 block text-sm font-semibold text-ink">{label}<input type="password" autoComplete={name === "current_password" ? "current-password" : "new-password"} className={field} {...password.register(name)} /></label>)}{Object.values(password.formState.errors).filter(Boolean).map((error, index) => error?.message && <p key={index} className="mt-1 text-xs text-error">{error.message}</p>)}{password.formState.errors.root && <p role="status" className={`mt-4 flex items-center gap-1.5 text-sm ${password.formState.errors.root.message?.startsWith("Đã") ? "text-brand" : "text-error"}`}><CheckCircle size={16} />{password.formState.errors.root.message}</p>}<Button type="submit" className="mt-5" disabled={password.formState.isSubmitting}>{password.formState.isSubmitting ? "Đang cập nhật..." : "Cập nhật mật khẩu"}</Button></form></div></div></div></section>;
}
