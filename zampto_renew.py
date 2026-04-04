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
    cf_iframe_selector = 'iframe[src*="challenges.cloudflare.com"]'
    
    try:
        # ---------------- 1. 登录 ----------------
        print(" -> 正在访问登录页面...")
        sb.maximize_window() # 【关键优化】最大化窗口，防止坐标偏移
        sb.uc_open_with_reconnect(LOGIN_URL, 4)
        time.sleep(5) 
        
        # --- 第 1 步：输入邮箱并点击下一步 ---
        print(" -> 填写账号...")
        account_input = 'input[name="identifier"], input[name="email"], input[type="email"], input[type="text"]'
        sb.wait_for_element_visible(account_input, timeout=15)
        sb.type(account_input, username)
        
        print(" -> 点击继续...")
        sb.click('button[type="submit"], button:contains("Sign in"), button.cl-formButtonPrimary')
        
        # 等待密码页面加载出来
        time.sleep(5)
        
        # --- 第 2 步：输入密码并处理验证 ---
        print(" -> 填写密码...")
        sb.wait_for_element_visible('input[type="password"]', timeout=15)
        sb.type('input[type="password"]', password)
        
        print(" -> 等待 Cloudflare 盾牌加载...")
        try:
            # 强制等待 CF 的 iframe 出现
            sb.wait_for_element_visible(cf_iframe_selector, timeout=10)
            time.sleep(3) # 等待内部动画渲染完成
            
            print(" -> 尝试点击验证码 (方案 A: 拟人化点击)...")
            sb.uc_click(cf_iframe_selector)
            time.sleep(2)
            
            print(" -> 尝试点击验证码 (方案 B: 物理坐标点击)...")
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f" -> 未检测到验证码或点击报错: {e}")
            
        print(" -> 等待验证通过 (休眠 12 秒)...")
        time.sleep(12)
            
        print(" -> 提交密码...")
        sb.click('button[type="submit"], button:contains("Continue"), button:contains("继续"), button:contains("Sign in")')
        
        print(" -> 等待控制台加载...")
        time.sleep(15) 
        
        # 校验是否成功登录
        if "dash.zampto.net" not in sb.get_current_url():
             sb.save_screenshot(f"{username}_login_failed.png")
             return False, f"❌ 账号 <b>{username}</b> 登录失败，验证码未通过或密码错误。"

        print(" -> 登录成功！")
        sb.save_screenshot(f"{username}_login_ok.png")

        # ---------------- 2. 依次处理多个服务 ----------------
        for idx, url in enumerate(RENEW_URLS):
            server_id = url.split('=')[-1]
            print(f" -> [服务 {server_id}] 正在打开面板...")
            
            sb.uc_open_with_reconnect(url, 3)
            time.sleep(6) 
            
            try:
                renew_btn = 'button:contains("Renew Server")'
                if sb.is_element_visible(renew_btn):
                    sb.click(renew_btn)
                    print(f" -> [服务 {server_id}] 已点击续期，处理验证码...")
                    
                    try:
                        sb.wait_for_element_visible(cf_iframe_selector, timeout=10)
                        time.sleep(3)
                        
                        print(f" -> [服务 {server_id}] 尝试拟人化点击...")
                        sb.uc_click(cf_iframe_selector)
                        time.sleep(2)
                        sb.uc_gui_click_captcha()
                    except:
                        pass
                    
                    print(f" -> [服务 {server_id}] 验证已触发，等待自动提交...")
                    time.sleep(15) # 弹窗的等待时间稍微加长一点
                    
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

    # 依然保持 uc=True 和 headless=False (依托于工作流里的 xvfb)
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
