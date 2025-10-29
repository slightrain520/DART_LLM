import requests
import json
import time

BASE_URL = "http://10.1.0.220:9002/api"
# 请根据实际端口修改BASE_URL

# 【重要！！！】 请修改 USER_NAME（把?替换为你的组号） 和 TOKEN（你的token）
# 所有接口的前缀：http://10.1.0.220:9002/
# 共享数据库的database_name：common_dataset（本数据库只允许查看，不允许删改，后端已做好限制）
# 共享数据库的metric_type：cosine（即默认选项）
# 共享数据库的token：token_common
# db_name:student_Group12_{our_dbname}
USER_NAME = "Group12"
TOKEN = "e-1qa4tLR9N_AnEEBemwaiOBoyoRoFHr00W0Wb3Uk5tWE5ziWJiCHh7sM1b73T2s"

# 1. 创建数据库
def test_create_database(metric_type="L2"):
    db_name = f"student_{USER_NAME}_{int(time.time())}"#测试创建数据库为时间戳后缀
    resp = requests.post(f"{BASE_URL}/databases", json={"database_name": db_name, "token": TOKEN, "metric_type": metric_type})
    print("创建数据库:", resp.status_code, resp.json())
    assert resp.status_code == 200
    return db_name, metric_type

# 2. 获取数据库列表
def test_get_databases():
    resp = requests.get(f"{BASE_URL}/databases", params={"token": TOKEN})
    print("获取数据库列表:", resp.status_code, resp.json())
    assert resp.status_code == 200
    return resp.json()["databases"]

# 3. 上传文件
def test_upload_file(db_name):
    payload = {
        "files": [
            {"file": "SQL注入即是指web应用程序对用户输入数据的合法性没有判断或过滤不严，攻击者可以在web应用程序中事先定义好的查询语句的结尾上添加额外的SQL语句，在管理员不知情的情况下实现非法操作，以此来实现欺骗数据库服务器执行非授权的任意查询，从而进一步得到相应的数据信息。", "metadata": {"description": "SQL注入概念"}},
            {"file": "sqlmap是一款自动化的SQL注入检测与利用工具，广泛用于发现和利用SQL注入漏洞。", "metadata": {"description": "SQLmap工具"}},
            {"file": "SQL注入是一种常见的Web安全漏洞，攻击者通过在用户输入的数据中注入恶意的SQL代码，从而实现对数据库的非法操作。", "metadata": {"description": "SQL注入攻击"}},
            {"file": "SQL注入的防御措施包括输入验证、参数化查询、最小权限原则等。", "metadata": {"description": "SQL注入防御措施"}},
            {"file": "SQL注入的防御措施包括输入验证、参数化查询、最小权限原则等。", "metadata": {"description": "SQL注入防御措施"}},
            {"file": "测试文件6", "metadata": {"description": "测试文件6"}},
            {"file": "测试文件7", "metadata": {"description": "测试文件7"}},
            {"file": "测试文件8", "metadata": {"description": "测试文件8"}},
            {"file": "测试文件9", "metadata": {"description": "测试文件9"}},
            {"file": "测试文件10", "metadata": {"description": "测试文件10"}},
        ],
        "token": TOKEN
    }
    resp = requests.post(f"{BASE_URL}/databases/{db_name}/files", json=payload)
    print("上传文件:", resp.status_code, resp.json())
    assert resp.status_code == 200
    return resp.json()["file_ids"] # 返回所有文件的id做后续测试

# 4. 查询数据库文件
def test_get_files(db_name):
    resp = requests.get(f"{BASE_URL}/databases/{db_name}/files", params={"token": TOKEN})
    print("查询数据库文件:", resp.status_code, resp.json())
    assert resp.status_code == 200
    return resp.json()["files"]

# 5. 相似文件检索
def test_search(db_name, metric_type, file_ids):
    # 测试1: 无过滤条件，返回top_k个结果
    print("\n测试1 - 无过滤条件搜索:")
    payload = {
        "token": TOKEN,
        "query": "SQL注入",
        "top_k": 5,
        "metric_type": metric_type
    }
    resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
    print("无过滤条件搜索:", resp.status_code, resp.json())
    assert resp.status_code == 200
    
    # 测试2: 使用单个file_id过滤（==操作符）
    print("\n测试2 - 单个file_id过滤 (==):")
    payload["expr"] = f"file_id == {file_ids[0]}"
    resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
    print("单个file_id过滤:", resp.status_code, resp.json())
    assert resp.status_code == 200
    
    # 测试3: 使用多个file_id过滤（in操作符）
    print("\n测试3 - 多个file_id过滤 (in):")
    file_ids_str = ", ".join(str(fid) for fid in file_ids[:3])  # 取前3个
    payload["expr"] = f"file_id in [{file_ids_str}]"
    resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
    print("多个file_id过滤:", resp.status_code, resp.json())
    assert resp.status_code == 200
    
    # 测试4: 不合法expr测试
    print("\n测试4 - 不合法expr测试:")
    payload["expr"] = "not_a_field == 123"
    resp = requests.post(f"{BASE_URL}/databases/{db_name}/search", json=payload)
    try:
        print("不合法expr相似文件检索:", resp.status_code, resp.json())
    except Exception:
        print("不合法expr相似文件检索: 非法响应", resp.status_code, resp.text)

# 6. 删除文件
def test_delete_file(db_name, file_id):
    resp = requests.delete(f"{BASE_URL}/databases/{db_name}/files/{file_id}", params={"token": TOKEN})
    print("删除文件:", resp.status_code, resp.json())
    assert resp.status_code == 200

# 7. 对话接口
def test_dialogue():
    payload = {
        "user_input": "请介绍一下网络安全的基本概念。",
        "token": TOKEN
    }
    resp = requests.post(f"{BASE_URL}/dialogue", json=payload)
    print("对话接口:", resp.status_code, resp.json())
    assert resp.status_code == 200

if __name__ == "__main__":
    # db_name, metric_type = test_create_database(metric_type="L2")
    dbs = test_get_databases()
    print(dbs)
    # file_ids = test_upload_file(db_name)
    # time.sleep(2)  # 等待Milvus flush
    # files = test_get_files(db_name)
    # test_search(db_name, metric_type, file_ids)
    # test_delete_file(db_name, file_ids[0])
    # test_dialogue()
    # print("所有接口测试完成！") 