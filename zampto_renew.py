import os
import time
import requests
from seleniumbase import SB

# ================= 配置区域 =================
# 登录页和续期页面的 URL (请根据实际情况修改)
LOGIN_URL = "https://zampto.com/login"  # 替换为真实的登录地址
RENEW_URL = "https://zampto.com/dashboard"  # 替换为真实的面板或续期地址

# ================= 环境变量获取 =================
ZAMPTO_ACCOUNT = os.environ.get('ZAMPTO_ACCOUNT', '')
TG_BOT = os.environ.get('TG_BOT', '')
# 工作流中配置了将代理转发到本地 8080 端口
USE_PROXY = bool(os.environ.get('GOST_PROXY'))
LOCAL_PROXY = "http://127.0.0.1:8080" if USE_PROXY else None

def send_telegram_msg(message):
    """发送 Telegram 通知"""
    if not TG_BOT:
        print("未配置 TG_BOT 环境变量，跳过 Telegram 通知。")
        return
    try:
        # 假设 GitHub Secret 格式为: 123456789:ABCDefg...#12345678 (BotToken#ChatID)
        token, chat_id = TG_BOT.split('#')
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        print("Telegram 通知发送成功")
    except Exception as e:
        print(f"Telegram 通知发送失败: {e}")

def process_account(sb, username, password):
    """处理单个账号的续期逻辑"""
    print(f"开始处理账号: {username}")
    try:
        # 1. 访问登录页面
        sb.open(LOGIN_URL)
        time.sleep(2) # 等待页面加载
        
        # 2. 输入账号密码 (⚠️此处需替换为真实的 CSS 选择器)
        sb.type('input[name="username"]', username) # 替换用户名输入框选择器
        sb.type('input[name="password"]', password) # 替换密码输入框选择器
        
        # 3. 点击登录按钮 (⚠️此处需替换为真实的 CSS 选择器)
        sb.click('button[type="submit"]') # 替换登录按钮选择器
        
        # 等待登录成功并跳转
        time.sleep(5) 
        
        # 截图保存：此时在工作流目录中保存的 png 会被 artifacts 自动上传
        sb.save_screenshot(f"{username}_login_status.png")
        
        # 4. 检查是否登录成功 (可选，根据页面某个特征元素判断)
        # sb.assert_element('div.dashboard-welcome') 

        # 5. 跳转到续期页面或直接在当前页点击续期
        sb.open(RENEW_URL)
        time.sleep(3)
        
        # 6. 点击续期按钮 (⚠️此处需替换为真实的 CSS 选择器)
        # 判断续期按钮是否存在
        if sb.is_element_visible('button.renew-btn'): 
            sb.click('button.renew-btn')
            time.sleep(3)
            sb.save_screenshot(f"{username}_renew_success.png")
            return True, f"✅ 账号 <b>{username}</b> 续期成功！"
        else:
            sb.save_screenshot(f"{username}_renew_skip.png")
            return True, f"ℹ️ 账号 <b>{username}</b> 未找到续期按钮 (可能暂无需续期)。"

    except Exception as e:
        # 发生异常时截图保存现场
        error_msg = str(e).split('\n')[0]
        sb.save_screenshot(f"{username}_error.png")
        return False, f"❌ 账号 <b>{username}</b> 续期失败！错误信息: {error_msg}"

def main():
    if not ZAMPTO_ACCOUNT:
        print("未检测到账号信息，请检查 Secrets 配置。")
        return

    # 解析账号信息，支持多账号，每行一个。格式: username:password
    accounts = [line.strip() for line in ZAMPTO_ACCOUNT.split('\n') if line.strip()]
    print(f"共加载了 {len(accounts)} 个账号。")

    results_msg = ["<b>Zampto 自动续期报告</b>\n"]

    # 启动 SeleniumBase
    # uc=True 启用隐身/反反爬模式 (Undetected Chromedriver)
    # 因为外层使用了 xvfb-run，这里不需要强制开启 headless=True
    with SB(uc=True, proxy=LOCAL_PROXY) as sb:
        for acc in accounts:
            if ':' not in acc:
                print(f"账号格式错误，跳过: {acc}")
                continue
            
            username, password = acc.split(':', 1)
            success, msg = process_account(sb, username, password)
            results_msg.append(msg)
            
            # 多账号处理间隔
            time.sleep(2)

    # 汇总通知
    final_message = "\n".join(results_msg)
    print(final_message.replace("<b>", "").replace("</b>", "")) # 控制台输出去掉 HTML 标签
    send_telegram_msg(final_message)

if __name__ == "__main__":
    main()
