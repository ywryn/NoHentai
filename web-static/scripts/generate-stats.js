import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 数据文件路径
const DATA_DIR = path.join(__dirname, '../public/data');
const GALLERIES_PATH = path.join(DATA_DIR, 'galleries.json');
const TRANSLATIONS_PATH = path.join(DATA_DIR, 'translations.json');
const OUTPUT_PATH = path.join(DATA_DIR, 'stats.json');

// 读取 JSON 文件
function readJSON(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
}

// 计算分类统计
function calculateCategoryStats(galleries) {
    const fixedCategories = [
        "Doujinshi", "Manga", "Artist CG", "Game CG",
        "Western", "Non-H", "Image Set", "Cosplay",
        "Asian Porn", "Misc"
    ];

    const categoryCounts = {};
    fixedCategories.forEach(cat => categoryCounts[cat] = 0);

    galleries.forEach(item => {
        const category = item.category;
        if (categoryCounts.hasOwnProperty(category)) {
            categoryCounts[category]++;
        }
    });

    return {
        total_count: galleries.length,
        categories: categoryCounts
    };
}

// 计算标签统计
function calculateTagStats(galleries, translations, type) {
    const tagCounter = {};

    galleries.forEach(gallery => {
        const tags = gallery.tags || [];
        tags.forEach(tag => {
            if (typeof tag === 'string' && tag.startsWith(`${type}:`)) {
                tagCounter[tag] = (tagCounter[tag] || 0) + 1;
            }
        });
    });

    // 获取前 20 个最常见标签
    const topTags = Object.entries(tagCounter)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 20)
        .map(([tag, count]) => {
            const [namespace, value] = tag.split(':', 2);
            let tagDetail = null;

            try {
                tagDetail = translations.data
                    .find(item => item.namespace === namespace)?.data?.[value];
            } catch (e) {
                // 忽略翻译错误
            }

            return {
                tag: tag,
                namespace: namespace,
                value: value,
                count: count,
                tag_cn: tagDetail?.name || '',
                intro: tagDetail?.intro || '',
                links: tagDetail?.links || ''
            };
        });

    return topTags;
}

// 计算季度趋势
function calculateQuarterlyStats(galleries) {
    const quarterlyStatsPosted = {};
    const quarterlyStatsFavTime = {};

    galleries.forEach(gallery => {
        // 统计 posted 时间
        const posted = gallery.posted;
        if (posted) {
            try {
                const timestamp = parseInt(posted);
                const date = new Date(timestamp * 1000);
                const year = date.getUTCFullYear();
                const month = date.getUTCMonth() + 1;
                const quarter = Math.ceil(month / 3);
                const key = `${year}-Q${quarter}`;

                quarterlyStatsPosted[key] = (quarterlyStatsPosted[key] || 0) + 1;
            } catch (e) {
                // 忽略无效时间戳
            }
        }

        // 统计 favTime 时间
        const favTime = gallery.favTime;
        if (favTime) {
            try {
                const dateMatch = favTime.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (dateMatch) {
                    const year = parseInt(dateMatch[1]);
                    const month = parseInt(dateMatch[2]);
                    const quarter = Math.ceil(month / 3);
                    const key = `${year}-Q${quarter}`;

                    quarterlyStatsFavTime[key] = (quarterlyStatsFavTime[key] || 0) + 1;
                }
            } catch (e) {
                // 忽略解析错误
            }
        }
    });

    // 合并所有季度并排序
    const allQuarters = new Set([
        ...Object.keys(quarterlyStatsPosted),
        ...Object.keys(quarterlyStatsFavTime)
    ]);

    const quarterlyData = Array.from(allQuarters)
        .sort()
        .map(quarter => ({
            quarter,
            postedCount: quarterlyStatsPosted[quarter] || 0,
            favTimeCount: quarterlyStatsFavTime[quarter] || 0
        }));

    return quarterlyData;
}

// 计算热力图数据
function calculateHeatmapData(galleries) {
    const dayCount = {};

    galleries.forEach(gallery => {
        if (gallery.favTime) {
            try {
                const dateMatch = gallery.favTime.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (dateMatch) {
                    const dateKey = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
                    dayCount[dateKey] = (dayCount[dateKey] || 0) + 1;
                }
            } catch (e) {
                // 忽略解析错误
            }
        }
    });

    // 生成过去一年的数据
    const today = new Date();
    const oneYearAgo = new Date(today);
    oneYearAgo.setFullYear(today.getFullYear() - 1);

    // 找到起始日期（周日对齐）
    const startDate = new Date(oneYearAgo);
    startDate.setDate(startDate.getDate() - startDate.getDay());

    // 生成 matrix 数据
    const matrixData = [];
    const currentDate = new Date(startDate);

    while (currentDate <= today) {
        const dateKey = currentDate.toISOString().split('T')[0];
        const dayOfWeek = currentDate.getDay();
        const weekNumber = Math.floor((currentDate - startDate) / (7 * 24 * 60 * 60 * 1000));

        matrixData.push({
            x: weekNumber,
            y: dayOfWeek,
            v: dayCount[dateKey] || 0,
            d: dateKey
        });

        currentDate.setDate(currentDate.getDate() + 1);
    }

    // 计算颜色范围
    const values = matrixData.map(d => d.v).filter(v => v > 0);
    const maxValue = Math.max(...values, 1);

    return {
        data: matrixData,
        maxValue: maxValue
    };
}

// 主函数
function generateStats() {
    console.log('Reading data files...');
    const galleries = readJSON(GALLERIES_PATH);
    const translations = readJSON(TRANSLATIONS_PATH);

    console.log(`Loaded ${galleries.length} galleries`);

    console.log('Calculating category stats...');
    const categoryStats = calculateCategoryStats(galleries);

    console.log('Calculating tag stats...');
    const types = ["artist", "other", "female", "male", "character", "parody"];
    const tagStats = {};
    types.forEach(type => {
        console.log(`  - ${type} tags`);
        tagStats[type] = calculateTagStats(galleries, translations, type);
    });

    console.log('Calculating quarterly stats...');
    const quarterlyStats = calculateQuarterlyStats(galleries);

    console.log('Calculating heatmap data...');
    const heatmapData = calculateHeatmapData(galleries);

    // 组装最终结果
    const result = {
        generatedAt: new Date().toISOString(),
        stats: categoryStats,
        tags: tagStats,
        quarterly: quarterlyStats,
        heatmap: heatmapData
    };

    console.log('Writing stats.json...');
    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(result, null, 2), 'utf-8');

    console.log(`Stats generated successfully at ${OUTPUT_PATH}`);
    console.log(`File size: ${(fs.statSync(OUTPUT_PATH).size / 1024).toFixed(2)} KB`);
}

// 执行
try {
    generateStats();
    process.exit(0);
} catch (error) {
    console.error('Error generating stats:', error);
    process.exit(1);
}
