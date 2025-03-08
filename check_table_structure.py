import sqlite3

def check_table_structure(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取表结构信息
    cursor.execute("PRAGMA table_info(budget_edit_items)")
    columns = cursor.fetchall()
    
    # 检查是否存在custom_name字段
    has_custom_name = any(col[1] == 'custom_name' for col in columns)
    
    # 将结果写入文件
    with open("table_structure.txt", "w", encoding="utf-8") as f:
        f.write("Table structure of budget_edit_items:\n")
        for col in columns:
            f.write(str(col) + "\n")
        
        f.write(f"\nHas custom_name column: {has_custom_name}\n")
    
    conn.close()

if __name__ == "__main__":
    check_table_structure("database/database.db")
