#!/usr/bin/env python
"""测试依赖是否正确安装"""

import sys

def test_imports():
    """测试所有必要的包是否可以导入"""
    print("测试依赖安装...")
    
    required_packages = [
        ("PyQt6", "PyQt6"),
        ("requests", "requests"),
        ("bs4", "BeautifulSoup4"),
        ("PIL", "Pillow"),
        ("lxml", "lxml"),
        ("langgraph", "langgraph"),
        ("langchain", "langchain"),
        ("langchain_anthropic", "langchain-anthropic"),
        ("langchain_core", "langchain-core"),
        ("anthropic", "anthropic"),
    ]
    
    failed = []
    
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - 未安装")
            failed.append(package_name)
    
    if failed:
        print(f"\n⚠️  以下包未安装: {', '.join(failed)}")
        print("请运行: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ 所有依赖已正确安装！")
        return True


def test_config():
    """测试配置"""
    print("\n测试配置...")
    
    try:
        from config import Config
        
        if not Config.ANTHROPIC_API_KEY:
            print("⚠️  未配置 ANTHROPIC_API_KEY")
            print("   请在 config.py 中设置你的 API 密钥")
            print("   或设置环境变量: export ANTHROPIC_API_KEY='your-key'")
        else:
            print("✅ API密钥已配置")
        
        if Config.ENABLE_AI_AGENT:
            print("✅ AI Agent 功能已启用")
        else:
            print("ℹ️  AI Agent 功能未启用（传统模式）")
        
        return True
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False


def test_agent():
    """测试 Agent 是否可以初始化"""
    print("\n测试 AI Agent...")
    
    try:
        from agent import create_agent_graph
        graph = create_agent_graph()
        print("✅ AI Agent 初始化成功")
        return True
    except Exception as e:
        print(f"❌ AI Agent 初始化失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("桌面动物园 - 安装测试")
    print("=" * 50)
    print()
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_config():
        success = False
    
    if not test_agent():
        success = False
    
    print()
    print("=" * 50)
    
    if success:
        print("🎉 所有测试通过！可以运行 python main.py 启动应用")
    else:
        print("⚠️  部分测试未通过，请检查上述错误")
    
    print("=" * 50)
    
    sys.exit(0 if success else 1)
