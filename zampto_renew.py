import os
import time
import requests
from seleniumbase import SB

# ================= 配置区域 =================
# 使用你提供的真实登录地址
LOGIN_URL = "https://auth.zampto.net/sign-in?app_id=bmhk6c8qdqxphlyscztgl"

# 具体的服务续期页面列表（你可以根据需要继续添加）
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
        time.sleep(3) # 等待页面完全加载
        
        # --- 第 1 步：输入邮箱并点击下一步 ---
        print(" -> 填写账号...")
        # 兼容各种情况的输入框选择器
        sb.type('input[placeholder*="Email"], input[placeholder*="Username"], input:visible', username)
        
        # 点击第一页的 Sign in 按钮
        sb.click('button:contains("Sign in"), button:contains("登录"), button[type="submit"]')
        
        # 等待密码页面加载出来
        time.sleep(4)
        
        # --- 第 2 步：输入密码并处理验证 ---
        print(" -> 填写密码...")
        # 此时页面上应该出现了密码框
        sb.type('input[type="password"]', password)
        
        print(" -> 等待登录页 Cloudflare 验证...")
        time.sleep(3)
        try:
            sb.uc_gui_click_captcha() # 点击密码页的验证码空白框
        except:
            pass
            
        # 点击密码页的 继续/Sign in 按钮
        sb.click('button:contains("继续"), button:contains("Sign in"), button[type="submit"]')
        
        # 等待登录成功，跳转到控制台域名
        sb.wait_for_url_contains('dash.zampto.net', timeout=20)
        print(" -> 登录成功！")
        sb.save_screenshot(f"{username}_login_ok.png")

        # ---------------- 2. 依次处理多个服务 ----------------
        for idx, url in enumerate(RENEW_URLS):
            server_id = url.split('=')[-1]
            print(f" -> [服务 {server_id}] 正在打开面板...")
            
            # 在同一窗口打开服务页面
            sb.uc_open_with_reconnect(url, 3)
            time.sleep(4) # 等待页面加载
            
            try:
                # 寻找紫色的续期按钮
                renew_btn = 'button:contains("Renew Server")'
                if sb.is_element_visible(renew_btn):
                    sb.click(renew_btn)
                    print(f" -> [服务 {server_id}] 已点击续期，处理验证码...")
                    
                    # 处理弹窗里的 CF 验证
                    time.sleep(3)
                    try:
                        sb.uc_gui_click_captcha() # 点击弹窗里的空白框
                    except:
                        pass
                    
                    # 点击空白框后会自动提交，此处等待 10 秒让请求完成
                    print(f" -> [服务 {server_id}] 验证已触发，等待自动提交...")
                    time.sleep(10)
                    
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

    # 关键配置：uc=True 绕过检测，headless=False 配合 xvfb 提高成功率
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
