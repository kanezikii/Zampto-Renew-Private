import os
import time
import requests
from seleniumbase import SB

# ================= 配置区域 =================
LOGIN_URL = "https://auth.zampto.net/sign-in?app_id=bmhk6c8qdqxphlyscztgl"

RENEW_URLS = [
    "https://dash.zampto.net/server?id=5329",
    "https://dash.zampto.net/server?id=5331"
]

# ================= 环境变量 =================
ZAMPTO_ACCOUNT = os.environ.get('ZAMPTO_ACCOUNT', '')
TG_BOT = os.environ.get('TG_BOT', '')
USE_PROXY = os.environ.get('GOST_PROXY')
LOCAL_PROXY = "http://127.0.0.1:8080" if USE_PROXY else None

def send_telegram_msg(message):
    """发送 Telegram 通知"""
    if not TG_BOT:
        return
    try:
        token, chat_id = TG_BOT.split('#')
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"TG 通知发送失败: {e}")

def process_account(sb, username, password):
    """处理单个账号及其下的所有服务续期"""
    print(f"\n[+] 开始处理账号: {username}")
    account_report = [f"👤 账号: <b>{username}</b>"]
    
    try:
        # ---------------- 1. 登录 ----------------
        print(" -> 正在访问登录页面...")
        sb.maximize_window()
        sb.uc_open_with_reconnect(LOGIN_URL, 4)
        time.sleep(5) 
        
        # --- 第 1 步：输入邮箱并点击下一步 ---
        print(" -> 填写账号...")
        account_input = 'input[name="identifier"], input[name="email"], input[type="email"], input[type="text"]'
        sb.wait_for_element_visible(account_input, timeout=15)
        sb.type(account_input, username)
        
        print(" -> 点击第一步的继续按钮...")
        sb.click('button[type="submit"], button:contains("Sign in"), button.cl-formButtonPrimary')
        
        time.sleep(5)
        
        # --- 第 2 步：输入密码并处理验证 ---
        print(" -> 填写密码...")
        sb.wait_for_element_visible('input[type="password"]', timeout=15)
        sb.type('input[type="password"]', password)
        time.sleep(1)
        
        print(" -> 点击继续按钮，触发验证码...")
        try:
            sb.click('button[type="submit"], button:contains("Continue"), button:contains("继续"), button:contains("Sign in")')
        except:
            pass
            
        print(" -> 等待 Cloudflare 验证码框出现...")
        try:
            # 显式等待 iframe 出现
            sb.wait_for_element_visible('iframe', timeout=15)
            print("    [+] 验证码框已出现，准备执行拟人点击...")
            
            # 【关键修复1】强制将 iframe 滚动到屏幕正中央，防止云端 xvfb 坐标偏移导致点空
            sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", sb.find_element("iframe"))
            time.sleep(2)
            
            # 【关键修复2】只点一次！绝对不再死循环狂点。
            try:
                sb.uc_click('iframe') # 使用 UC 底层的高权限点击
            except:
                pass
                
            time.sleep(1)
            
            try:
                sb.uc_gui_click_captcha() # 官方的 PyAutoGUI 备用点击
            except:
                pass
                
            print("    [+] 点击动作已完成，耐心等待 25 秒让 CF 验证并自动跳转...")
            time.sleep(25)
        except Exception:
            print("    [+] 未等到验证码框，可能直接被信任了，等待跳转...")
            time.sleep(15)
        
        # 终极安全校验
        if "dash.zampto.net" not in sb.get_current_url():
             sb.save_screenshot(f"{username}_login_failed.png")
             return False, f"❌ 账号 <b>{username}</b> 登录失败，未能成功跳转到控制台。"

        print(" -> 登录成功！")
        sb.save_screenshot(f"{username}_login_ok.png")

        # ---------------- 2. 依次处理多个服务 ----------------
        for idx, url in enumerate(RENEW_URLS):
            server_id = url.split('=')[-1]
            print(f"\n -> [服务 {server_id}] 正在打开面板...")
            
            sb.uc_open_with_reconnect(url, 3)
            time.sleep(8) 
            
            # 处理 Google 弹窗广告
            if "google_vignette" in sb.get_current_url():
                print(f" -> [服务 {server_id}] 拦截到广告，尝试跳过...")
                try:
                    sb.click('div:contains("Close"), span:contains("Close")')
                    time.sleep(2)
                except:
                    pass
                if "google_vignette" in sb.get_current_url():
                    sb.refresh()
                    time.sleep(8)
            
            try:
                renew_btn = 'button:contains("Renew Server")'
                if sb.is_element_visible(renew_btn):
                    sb.click(renew_btn)
                    print(f" -> [服务 {server_id}] 已点击续期，处理弹窗验证码...")
                    time.sleep(4)
                    
                    try:
                        if sb.is_element_visible('iframe'):
                            # 弹窗里的验证码也执行居中校准
                            sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", sb.find_element("iframe"))
                            time.sleep(1)
                            try:
                                sb.uc_click('iframe')
                            except:
                                pass
                            try:
                                sb.uc_gui_click_captcha()
                            except:
                                pass
                    except:
                        pass
                    
                    print(f" -> [服务 {server_id}] 续期验证已触发，等待 15 秒确认...")
                    time.sleep(15) 
                    
                    sb.save_screenshot(f"{username}_server_{server_id}_done.png")
                    account_report.append(f"  ✅ ID {server_id}: 续期已提交")
                else:
                    sb.save_screenshot(f"{username}_server_{server_id}_no_btn.png")
                    account_report.append(f"  ℹ️ ID {server_id}: 未找到续期按钮 (可能暂无需续期)")
            except Exception as e:
                account_report.append(f"  ❌ ID {server_id}: 处理出错")
                print(f" -> [服务 {server_id}] 错误: {e}")

        return True, "\n".join(account_report)

    except Exception as e:
        sb.save_screenshot(f"{username}_fatal_error.png")
        return False, f"❌ 账号 <b>{username}</b> 流程崩溃: {str(e)[:100]}"

def main():
    if not ZAMPTO_ACCOUNT:
        print("错误: 未配置 ZAMPTO_ACCOUNT 环境变量")
        return

    accounts = [line.strip() for line in ZAMPTO_ACCOUNT.split('\n') if line.strip()]
    final_reports = ["<b>Zampto 自动化续期报告</b>"]

    with SB(uc=True, proxy=LOCAL_PROXY, headless=False) as sb:
        for acc in accounts:
            if ':' not in acc: continue
            user, pwd = acc.split(':', 1)
            success, report = process_account(sb, user, pwd)
            final_reports.append(report)
            time.sleep(5)

    full_msg = "\n\n".join(final_reports)
    print(full_msg.replace("<b>", "").replace("</b>", ""))
    send_telegram_msg(full_msg)

if __name__ == "__main__":
    main()
