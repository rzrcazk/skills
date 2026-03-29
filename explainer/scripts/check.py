#!/usr/bin/env python3
"""
Manim 教学视频代码检查脚本
验证 script.py 是否包含必要的函数和结构

使用方法:
    python scripts/check.py [script_file]

默认检查 script.py，也可以指定其他文件
"""

import ast
import sys
import os
from pathlib import Path


class CodeChecker:
    """代码结构检查器"""

    # 必须包含的函数
    REQUIRED_FUNCTIONS = [
        'calculate_geometry',
        'assert_geometry',
        'define_elements',
    ]

    # 推荐包含的函数（警告但不阻止）
    RECOMMENDED_FUNCTIONS = [
        'play_scene',
    ]

    # 必须包含的类（内部类也算）
    REQUIRED_CLASSES = [
        'Subtitle',
        'TitleSubtitle',
    ]

    # 布局相关的变量名（用于布局检查）
    LAYOUT_PATTERNS = [
        'SUBTITLE_Y',
        'FORMULA_Y',
        'GRAPHIC_CENTER',
        'MIN_SPACING',
    ]

    # 内容深度相关的禁止模式（初中水平）
    JUNIOR_HIGH_FORBIDDEN = [
        r'3\*\*2\s*=\s*9',  # 3**2 = 9
        r'3²\s*=\s*9',     # 3² = 9
        r'4\*\*2\s*=\s*16', # 4**2 = 16
        r'4²\s*=\s*16',    # 4² = 16
        r'5\*\*2\s*=\s*25', # 5**2 = 25
        r'5²\s*=\s*25',    # 5² = 25
    ]

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.errors = []
        self.warnings = []
        self.tree = None
        self.classes = {}  # 类名 -> 方法列表
        self.source_code = ""  # 源代码内容

    def parse(self):
        """解析 Python 文件"""
        if not self.file_path.exists():
            self.errors.append(f"文件不存在: {self.file_path}")
            return False

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
            self.tree = ast.parse(self.source_code)
            return True
        except SyntaxError as e:
            self.errors.append(f"语法错误: {e}")
            return False
        except Exception as e:
            self.errors.append(f"解析失败: {e}")
            return False

    def analyze(self):
        """分析代码结构"""
        if not self.tree:
            return

        # 遍历顶层定义
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                methods = []
                inner_classes = []

                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                    elif isinstance(item, ast.ClassDef):
                        inner_classes.append(item.name)
                        # 也记录内部类的方法
                        inner_methods = [n.name for n in item.body
                                        if isinstance(n, ast.FunctionDef)]
                        self.classes[f"{class_name}.{item.name}"] = inner_methods

                self.classes[class_name] = methods

    def check_required_functions(self):
        """检查必需函数是否存在"""
        all_methods = set()
        for class_name, methods in self.classes.items():
            all_methods.update(methods)

        for func_name in self.REQUIRED_FUNCTIONS:
            if func_name not in all_methods:
                self.errors.append(
                    f"缺少必需函数: {func_name}()\n"
                    f"  请在 MathScene 类中实现此方法\n"
                    f"  作用: {self._get_function_description(func_name)}"
                )

    def check_recommended_functions(self):
        """检查推荐函数"""
        all_methods = set()
        for class_name, methods in self.classes.items():
            all_methods.update(methods)

        for func_name in self.RECOMMENDED_FUNCTIONS:
            if func_name not in all_methods:
                self.warnings.append(
                    f"缺少推荐函数: {func_name}()\n"
                    f"  建议实现以更好地控制每幕动画"
                )

    def check_subtitle_classes(self):
        """检查字幕类是否存在"""
        # 检查 Subtitle 和 TitleSubtitle 是否作为内部类定义
        found_subtitle = False
        found_title = False

        for class_name in self.classes.keys():
            if '.' in class_name:
                outer, inner = class_name.split('.')
                if inner == 'Subtitle':
                    found_subtitle = True
                if inner == 'TitleSubtitle':
                    found_title = True

        if not found_subtitle:
            self.warnings.append(
                "未找到 Subtitle 类\n"
                "  建议: 从 templates/script_scaffold.py 复制 Subtitle 类定义\n"
                "  作用: 避免忘记渲染/退场导致的文字残留问题"
            )

        if not found_title:
            self.warnings.append(
                "未找到 TitleSubtitle 类\n"
                "  建议: 从 templates/script_scaffold.py 复制 TitleSubtitle 类定义"
            )

    def check_scene_class(self):
        """检查是否有场景类继承自 Scene"""
        found_scene = False
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'Scene':
                        found_scene = True
                        break
                    elif isinstance(base, ast.Attribute):
                        if base.attr == 'Scene':
                            found_scene = True
                            break

        if not found_scene:
            self.errors.append(
                "未找到继承自 Scene 的类\n"
                "  必须有一个类继承自 Scene，例如: class ExplainerScene(Scene):"
            )

    def check_add_sound(self):
        """检查是否有 add_sound 调用（音频集成）"""
        has_add_sound = False

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'add_sound':
                        has_add_sound = True
                        break
                elif isinstance(node.func, ast.Name):
                    if node.func.id == 'add_sound':
                        has_add_sound = True
                        break

        if not has_add_sound:
            self.warnings.append(
                "未检测到 add_sound() 调用\n"
                "  提醒: 每幕动画应该添加对应的音频文件\n"
                "  示例: self.add_sound('audio/audio_001_开场.wav')"
            )

    def check_layout_constraints(self):
        """检查布局约束是否存在"""
        has_layout = False
        for pattern in self.LAYOUT_PATTERNS:
            if pattern in self.source_code:
                has_layout = True
                break

        if not has_layout:
            self.warnings.append(
                "未检测到布局约束定义\n"
                "  建议: 定义 SUBTITLE_Y, FORMULA_Y, GRAPHIC_CENTER 等常量\n"
                "  作用: 确保文字与图形不重叠，避免布局混乱"
            )

    def check_content_depth(self):
        """检查内容深度（初中水平避免过于基础的计算）"""
        import re

        found_basic_calculations = []
        for pattern in self.JUNIOR_HIGH_FORBIDDEN:
            if re.search(pattern, self.source_code):
                found_basic_calculations.append(pattern)

        if found_basic_calculations:
            self.warnings.append(
                "检测到过于基础的计算展示（初中水平）\n"
                "  问题: 直接展示 3²=9, 4²=16 等计算对初中生太简单\n"
                "  建议: 直接给出 3²+4²=5²，重点讲解几何意义和证明\n"
                "  参考: SKILL.md 中的内容深度控制章节"
            )

    def check_proof_visualization(self):
        """检查证明动画是否有可视化"""
        # 检查是否有证明相关的场景
        has_proof = 'proof' in self.source_code.lower() or '证明' in self.source_code

        if has_proof:
            # 检查是否有步骤性的动画
            proof_patterns = ['play_scene_', 'animate', 'Transform']
            has_animation = any(p in self.source_code for p in proof_patterns)

            if not has_animation:
                self.warnings.append(
                    "检测到证明相关内容但动画可能不足\n"
                    "  建议: 证明过程需要分步骤动画展示\n"
                    "  要求: 每步必须有对应图形变化，等式推导必须可视化"
                )

    def _get_function_description(self, func_name):
        """获取函数描述"""
        descriptions = {
            'calculate_geometry': '计算所有几何元素（点、线、圆）的坐标和属性',
            'assert_geometry': '验证几何计算的正确性和画布范围',
            'define_elements': '定义 Manim 图形对象（点、线、圆等）',
        }
        return descriptions.get(func_name, '未知功能')

    def run(self):
        """运行所有检查"""
        print(f"🔍 检查文件: {self.file_path}")
        print("=" * 50)

        # 解析
        if not self.parse():
            return False

        # 分析
        self.analyze()

        # 各项检查
        self.check_scene_class()
        self.check_required_functions()
        self.check_recommended_functions()
        self.check_subtitle_classes()
        self.check_add_sound()
        self.check_layout_constraints()
        self.check_content_depth()
        self.check_proof_visualization()

        # 输出结果
        return self.report()

    def report(self):
        """输出检查报告"""
        success = len(self.errors) == 0

        # 错误
        if self.errors:
            print("\n❌ 错误 (必须修复):")
            for i, error in enumerate(self.errors, 1):
                print(f"\n  {i}. {error}")

        # 警告
        if self.warnings:
            print("\n⚠️  警告 (建议修复):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"\n  {i}. {warning}")

        # 成功信息
        if success and not self.warnings:
            print("\n✅ 所有检查通过！可以开始渲染。")
        elif success:
            print("\n✅ 必要检查通过，但有警告建议处理。")

        print("\n" + "=" * 50)

        if success:
            print("🎬 下一步: 运行渲染命令")
            print(f"   manim -pqh {self.file_path} ExplainerScene")
        else:
            print("⛔ 检查失败，请修复错误后重试。")

        return success


def main():
    """主函数"""
    # 获取要检查的文件
    if len(sys.argv) > 1:
        script_file = sys.argv[1]
    else:
        script_file = "script.py"

    # 检查文件路径
    script_path = Path(script_file)

    # 运行检查
    checker = CodeChecker(script_path)
    success = checker.run()

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
