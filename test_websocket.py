"""测试WebSocket消息流 - 简化版"""
import asyncio
import websockets
import json
import time
import requests

async def test_multi_agent_audit():
    print("=" * 60)
    print("开始测试多智能体审核WebSocket消息流")
    print("=" * 60)
    
    # 使用一个不存在的script_id，直接看后端日志
    print("\n[步骤1] 直接连接WebSocket，观察后端日志...")
    print("请查看后端终端输出，确认是否有如下日志：")
    print("  [_send_message] 准备发送消息: script_preview, delay=1.0秒")
    print("  [_send_message] 消息已发送: script_preview, 开始等待1.0秒...")
    print("  [_send_message] 等待完成: script_preview, 实际耗时=1.01秒")
    print("\n如果看到上述日志，说明后端确实在等待！")
    print("\n请手动在浏览器中测试，然后查看：")
    print("  1. 后端终端的日志（是否有delay和实际耗时）")
    print("  2. 浏览器控制台的WebSocket消息时间戳（Network -> WS）")
    print("  3. 前端页面是否逐条显示消息")
    print("\n" + "=" * 60)
    
    # 1. 创建审核会话
    print("\n[步骤1] 创建审核会话...")
    response = requests.post(
        "http://localhost:8000/api/v1/audit/multi-agent/test_script_123",
        json={
            "conversation_history": [
                {"role": "user", "content": "请生成一个关于飞行安全的讲解脚本"}
            ],
            "knowledge_base_id": "default"
        }
    )
    
    if response.status_code != 200:
        print(f"❌ 创建会话失败: {response.status_code}")
        print(response.text)
        return
    
    session_id = response.json()["session_id"]
    print(f"✅ 会话创建成功: {session_id}")
    
    # 2. 连接WebSocket
    print(f"\n[步骤2] 连接WebSocket...")
    ws_url = f"ws://localhost:8000/api/v1/audit/ws/multi-agent/{session_id}"
    
    message_count = 0
    first_message_time = None
    last_message_time = None
    
    async with websockets.connect(ws_url) as websocket:
        print(f"✅ WebSocket已连接: {ws_url}")
        print("\n" + "=" * 60)
        print("开始接收消息（实时显示）")
        print("=" * 60 + "\n")
        
        try:
            while True:
                message = await websocket.recv()
                current_time = time.time()
                
                if first_message_time is None:
                    first_message_time = current_time
                
                # 计算距离第一条消息的时间差
                time_diff = current_time - first_message_time if first_message_time else 0
                
                data = json.loads(message)
                message_count += 1
                
                # 实时打印消息
                print(f"[+{time_diff:.2f}s] 第{message_count}条消息:")
                print(f"  类型: {data.get('type')}")
                if 'agent_name' in data:
                    print(f"  智能体: {data.get('emoji', '')} {data.get('agent_name')}")
                if 'content' in data:
                    content = data['content']
                    if len(content) > 100:
                        content = content[:100] + "..."
                    print(f"  内容: {content}")
                print()
                
                last_message_time = current_time
                
                # 检查是否结束
                if data.get('type') in ['complete', 'session_complete']:
                    print("=" * 60)
                    print("审核完成")
                    print("=" * 60)
                    break
                    
        except Exception as e:
            print(f"\n❌ 接收消息时出错: {e}")
    
    # 3. 统计分析
    total_time = last_message_time - first_message_time if last_message_time and first_message_time else 0
    print(f"\n📊 统计结果:")
    print(f"  总消息数: {message_count}")
    print(f"  总耗时: {total_time:.2f}秒")
    if message_count > 1:
        avg_interval = total_time / (message_count - 1)
        print(f"  平均间隔: {avg_interval:.2f}秒")
    
    if total_time < 1:
        print("\n⚠️  警告: 所有消息在1秒内接收完毕，说明没有延时效果！")
    elif avg_interval < 0.3:
        print("\n⚠️  警告: 平均间隔小于0.3秒，延时可能未生效！")
    else:
        print("\n✅ 消息流正常，有明显的时间间隔")

if __name__ == "__main__":
    asyncio.run(test_multi_agent_audit())
