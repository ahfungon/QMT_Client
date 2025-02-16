import shutil
from pathlib import Path
from datetime import datetime
from src.config import config

def backup_positions():
    """备份持仓数据"""
    source = Path(config.get('data.positions_file'))
    if not source.exists():
        return
        
    # 创建备份目录
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"positions_{timestamp}.json"
    
    # 复制文件
    shutil.copy2(source, backup_file)
    
    # 清理旧备份（保留最近30个）
    backup_files = sorted(backup_dir.glob("positions_*.json"))
    if len(backup_files) > 30:
        for file in backup_files[:-30]:
            file.unlink()

if __name__ == "__main__":
    backup_positions() 