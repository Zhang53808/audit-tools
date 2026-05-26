"""函证地址核查 - CLI 入口。"""

import os
import sys

import click

from audit_tools.common.logging import setup_logging, get_logger

logger = get_logger(__name__)


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="输出 Excel 路径")
@click.option("--map-key", default=None, help="腾讯地图 API Key")
@click.option("--llm-key", default=None, help="LLM API Key (DeepSeek/OpenAI 兼容)")
@click.option("--llm-model", default=None, help="LLM 模型名称")
@click.option("--llm-base-url", default=None, help="LLM 服务地址")
@click.option("--anysearch-cli", default=None, help="AnySearch CLI 路径")
@click.option("--no-search", is_flag=True, help="跳过第2层搜索")
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
@click.option("--dotenv", is_flag=True, help="加载 .env 文件")
def main(
    input_file, output, map_key, llm_key, llm_model, llm_base_url,
    anysearch_cli, no_search, verbose, dotenv,
):
    """函证地址核查 - 三层过滤异常初筛器。

    INPUT_FILE: 含「公司名称」「发函地址」「工商注册地址」的 Excel 文件。
    """
    setup_logging(level="DEBUG" if verbose else "INFO")

    # 加载 .env
    if dotenv:
        try:
            from dotenv import load_dotenv
            script_dir = os.path.dirname(os.path.abspath(__file__))
            for _ in range(3):  # go up to project root
                env_path = os.path.join(script_dir, ".env")
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    break
                script_dir = os.path.dirname(script_dir)
        except ImportError:
            pass

    # 环境变量后备
    map_key = map_key or os.getenv("TENCENT_MAP_KEY", "")
    llm_key = llm_key or os.getenv("DEEPSEEK_API_KEY", "")
    llm_base_url = llm_base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_model = llm_model or os.getenv("LLM_MODEL", "deepseek-chat")
    anysearch_cli = anysearch_cli or os.getenv("ANYSEARCH_CLI", "")

    if not map_key:
        logger.warning("未配置腾讯地图 API Key，第1.5层（地理编码）将跳过")
    if not llm_key:
        logger.info("未配置 LLM API Key，第2层将使用域名白名单降级模式")

    from audit_tools.address_verification.engine import verify_addresses

    verify_addresses(
        input_file,
        output_file=output,
        skip_search=no_search,
        map_key=map_key,
        llm_key=llm_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        anysearch_cli=anysearch_cli,
    )


if __name__ == "__main__":
    main()
