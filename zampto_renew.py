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
        sb.uc_open_with_reconnect(LOGIN_URL, 4)
        time.sleep(5) 
        
        # --- 第 1 步：输入邮箱并点击下一步 ---
        print(" -> 填写账号...")
        account_input_selector = 'input[name="identifier"], input[name="email"], input[type="email"], input[type="text"]'
        
        sb.wait_for_element_visible(account_input_selector, timeout=15)
        sb.type(account_input_selector, username)
        
        print(" -> 点击继续...")
        sb.click('button[type="submit"], button:contains("Sign in"), button.cl-formButtonPrimary')
        
        # 等待密码页面加载出来
        time.sleep(5)
        
        # --- 第 2 步：输入密码并处理验证 ---
        print(" -> 填写密码...")
        sb.wait_for_element_visible('input[type="password"]', timeout=15)
        sb.type('input[type="password"]', password)
        
        print(" -> 等待 Cloudflare 盾牌加载...")
        time.sleep(5)
        
        # 【新增】：向下滚动页面，确保验证码在可视范围内
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        print(" -> 尝试点击验证码 (方案 A)...")
        try:
            sb.uc_gui_click_captcha()
        except:
            pass
            
        time.sleep(2)
        
        # 【新增】：备用点击方案，直接强制点击页面上的 iframe（即验证码本身）
        print(" -> 尝试点击验证码 (方案 B - 强制点击)...")
        try:
            if sb.is_element_visible('iframe'):
                sb.click('iframe')
        except:
            pass
            
        print(" -> 等待验证通过 (休眠 12 秒)...")
        time.sleep(12)
            
        print(" -> 提交密码...")
        sb.click('button[type="submit"], button:contains("Continue"), button:contains("继续"), button:contains("Sign in")')
        
        print(" -> 等待控制台加载...")
        time.sleep(15) 
        
        # 校验是否成功登录
        if "dash.zampto.net" not in sb.get_current_url():
             sb.save_screenshot(f"{username}_login_failed.png")
             return False, f"❌ 账号 <b>{username}</b> 登录失败，卡在验证码或密码错误。"

        print(" -> 登录成功！")
        sb.save_screenshot(f"{username}_login_ok.png")

        # ---------------- 2. 依次处理多个服务 ----------------
        for idx, url in enumerate(RENEW_URLS):
            server_id = url.split('=')[-1]
            print(f" -> [服务 {server_id}] 正在打开面板...")
            
            sb.uc_open_with_reconnect(url, 3)
            time.sleep(5) 
            
            try:
                renew_btn = 'button:contains("Renew Server")'
                if sb.is_element_visible(renew_btn):
                    sb.click(renew_btn)
                    print(f" -> [服务 {server_id}] 已点击续期，处理验证码...")
                    
                    time.sleep(4)
                    
                    # 弹窗里的验证码同样加上双重点击保险
                    try:
                        sb.uc_gui_click_captcha()
                    except:
                        pass
                    time.sleep(1)
                    try:
                        if sb.is_element_visible('iframe'):
                            sb.click('iframe')
                    except:
                        pass
                    
                    print(f" -> [服务 {server_id}] 验证已触发，等待自动提交...")
                    time.sleep(12)
                    
                    sb.save_screenshot(f"{username}_server_{server_id}_done.png")
                    account_report.append(f"  ✅ ID {server_id}: 续期已提交")
                else:
                    sb.save_screenshot(f"{username}_server_{server_id}_no_btn.png")
                    account_report.append(f"  ℹ️ ID {server_id}: 未找到续期按钮")
            except Exception as e:
                account_report.append(f"  ❌ ID {server_id}: 处理出错")
                print(f" -> [服务 {server_id}] 错误信息: {e}")

        return True, "\n".join(account_report)

    except Exception as e:
        sb.save_screenshot(f"{username}_fatal_error.png")
        return False, f"❌ 账号 <b>{username}</b> 流程中断: {str(e)[:100]}"

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
