# B站市集爬虫

[English README](README.md) | [中文 README](README.zh.md)

## 概述

**B站市集爬虫** 是一个基于 Python 的网页爬取工具，专门用于从B站市集中提取商品信息。它可以根据指定的条件（如商品名称、价格范围、折扣率和类别）查找你喜欢的商品。

## 功能特点

- **可定制的商品搜索**：支持按商品名称、价格范围、折扣率和类别筛选。
- **自动化数据存储**：爬取的数据会自动保存到 CSV 文件和 SQLite 数据库。

## 项目结构

```
├── main.py          # 主爬虫脚本
├── db.py            # 处理 SQLite 数据库操作的函数
├── tools.py         # 辅助工具函数
├── sort_total.sh    # 用于排序 CSV 文件的 Shell 脚本
├── main.sh          # 封装主爬虫脚本的 Shell 脚本（适合 Shell 爱好者）
├── cookies.txt      # 存放B站账户 Cookies 的文本文件
├── bilidata.db      # SQLite 数据库（运行爬虫后自动生成）
├── total_*.csv      # 包含所有爬取的商品信息的 CSV 文件（运行爬虫后生成）
└── want_*.csv       # 包含筛选后的商品信息的 CSV 文件（运行爬虫后生成）
```

## 安装

1. **克隆仓库：**
   ```bash
   git clone https://github.com/Shujian-He/BiliMagicMarketScraper.git
   cd BiliMagicMarketScraper
   ```

2. **安装依赖：**
   ```bash
   pip3 install requests
   ```

3. **设置 Cookies：**
   - 该爬虫需要使用你的B站账户的 Cookies 进行身份验证，以访问市集 API。
   - 打开 `cookies.txt`，将占位符替换为你的实际 Cookies。
   - 你可以在浏览器的开发者工具中获取 Cookies：
     1. 登录B站主站 (https://www.bilibili.com/)，并访问市集页面：https://mall.bilibili.com/neul-next/index.html?page=magic-market_index。
     2. 按 `F12` 打开开发者工具，找到 **Network** 选项卡。
     3. 刷新页面（Windows：`Ctrl+R`，macOS：`command+R`），然后点击左侧的 `list` 文件。
     4. 进入 **Headers** - **Request Headers**，复制 **Cookie:** 之后的所有内容。

## 使用方法

运行爬虫：

```sh
python3 main.py -w <商品名称> -p <价格范围> -d <折扣范围> -c <类别>
```

如果你是 Shell 爱好者，可使用 Shell ：

```sh
sh main.sh -w <商品名称> -p <价格范围> -d <折扣范围> -c <类别>
```

### 参数说明：

- `-w, --want`：想要的一个或多个商品名称。（默认：`初音未来`）
- `-p, --price`：价格范围（单位：分）。（默认：`6000-10000`）
- `-d, --discount`：折扣百分比范围。（默认：`0-100`）
- `-c, --category`：商品类别。具体如下。（默认：`2312`）
  - `2312`：手办
  - `2066`：模型
  - `2331`：周边
  - `2273`：3C 数码
  - `fudai_cate_id`：福袋

### 使用示例：

```sh
python3 main.py -w 初音未来 孤独摇滚 -p 5000-15000 -d 10-50
```

或

```sh
sh main.sh -w fufu -p 5000-50000 -d 0-100 -c 2331
```

运行后将生成两个 CSV 文件：`total_*.csv` 和 `want_*.csv`，同时数据也会自动存入 SQLite 数据库 `bilidata.db`。

爬取完成后程序会自动停止，或者你可以按 `Ctrl+C` 手动停止。

## 关于数据

### CSV 文件

生成的 CSV 文件包含 6 列，**无**表头：

| 列名 | 描述 | 示例 |
|-|-|-|
| **时间戳** | 采集时间戳 | `2025-02-01 16:04:41.964444` |
| **商品名称** | 商品名称 | `S-FIRE 初音未来 秋日之约Ver. 正比手办` |
| **商品 ID** | 商品的唯一标识符 | `142389472138` |
| **当前价格** | 以分为单位的当前价格 | `34344` |
| **原价** | 以分为单位的原价 | `50500` |
| **折扣率** | 折扣率 | `0.6800792079207921` |

- 你可以通过以下命令对 CSV 文件进行排序：
  
  ```bash
  sh sort_total.sh
  ```
  
  这将生成两个排序后的文件：`sort_total_*.csv` 和 `sort_want_*.csv`。

### 数据库
数据库表结构如下：

| 列名 | 类型 | 描述 |
|-|-|-|
| `id` | TEXT | 商品唯一标识符（主键） |
| `name` | TEXT | 商品名称 |
| `price` | INTEGER | 以分为单位的当前价格 |
| `market_price` | INTEGER | 以分为单位的原价 |
| `rate` | REAL | 折扣率 |
| `time` | TEXT | 采集时间戳 |

你可以使用 `DB Browser for SQLite` 或直接使用 Python 来查询数据库。

- 如果主脚本发生错误，你可以手动运行以下命令将 CSV 数据存入数据库：

    ```sh
    python3 db.py
    ```

## 如何使用数据

你可以通过商品 ID 直接访问特定商品，在浏览器中使用以下链接，并将 `<REPLACE_THIS_WITH_PRODUCT_ID>` 替换为具体商品 ID：

```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=<REPLACE_THIS_WITH_PRODUCT_ID>&from=market_index
```

例如：

```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=142389472138&from=market_index
```

## 许可证

本项目基于 MIT 许可证发布，详情请查看 [LICENSE](LICENSE) 文件。

## 致谢

特别感谢 ChatGPT 帮助进行了代码编写以及文档整理和翻译。
