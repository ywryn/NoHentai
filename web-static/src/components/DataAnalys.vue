<template>
    <div class="container">

        <!-- 网站说明 -->
        <div class="site-description">
            <p><span class="site-name">NoHentai</span>：ExHentai/E-Hentai 个人收藏&同步网站。支持数据分析（包括分类分布、季度趋势以及不同命名空间下的热门标签统计）、Gallery高级检索、E/Ex数据源同步。</p>
        </div>

        <!-- 收藏活动热力图 -->
        <div class="heatmap-section">
            <div class="heatmap-content">
                <h2 class="section-title">Favorite Activity</h2>
                <div class="heatmap-chart-container">
                    <Chart type="matrix" :data="heatmapChartData" :options="heatmapChartOptions" class="heatmap-chart" />
                </div>
            </div>
        </div>

        <!-- 顶部行：Statistics (左) 和 Categories (右) -->
        <div class="stats-row">
            <div class="stats-left">
                <h1 class="section-title-large">Gallery Statistics</h1>
                <div class="stats-row-inline">
                    <p class="stats-text">
                        Total Galleries: {{ stats.total_count }}
                    </p>
                    <div class="toggle-wrapper">
                        <span class="toggle-label">Show All</span>
                        <ToggleSwitch v-model="showFullData" @change="toggleFullData" />
                    </div>
                </div>
                <div class="line-chart-container">
                    <Chart type="line" :data="quarterlyLineData" :options="quarterlyLineOptions"
                        class="chart-full" />
                </div>
            </div>
            <div class="stats-right">
                <h2 class="section-title">Categories</h2>
                <div class="chart-container">
                    <Chart type="pie" :data="chartData" :options="chartOptions" class="chart-responsive" />
                </div>
            </div>
        </div>

        <!-- 中间行：Female Tags (左) 和 Male Tags (右) -->
        <div class="tags-row">
            <div class="tags-section-half">
                <h2 class="section-title">Female Tags</h2>
                <div class="chart-container">
                    <Chart type="bar" :data="femaleChartData" :options="barChartOptions" class="chart-responsive" />
                </div>
            </div>
            <div class="tags-section-half">
                <h2 class="section-title">Male Tags</h2>
                <div class="chart-container">
                    <Chart type="bar" :data="maleChartData" :options="barChartOptions" class="chart-responsive" />
                </div>
            </div>
        </div>

        <!-- 底部行 -->
        <div class="bottom-row">
            <div class="bottom-section">
                <h2 class="section-title">Other</h2>
                <table class="data-table">
                    <colgroup>
                        <col class="tag-col">
                        <col class="count-col">
                    </colgroup>
                    <thead>
                        <tr>
                            <th class="left-align">Tag</th>
                            <th class="right-align">Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="tag in tags.other" :key="tag.tag" v-tooltip.bottom="[
                            `${tag.tag}`,
                            `翻译: ${tag.tag_cn || 'N/A'}`,
                            tag.intro ? `介绍: ${tag.intro.length > 100 ? tag.intro.slice(0, 100) + '...' : tag.intro}` : null
                        ].filter(Boolean).join('\n')">
                            <td class="left-align">
                                {{ tag.tag_cn || tag.tag.replace(/^language:/, '') }}
                            </td>
                            <td class="right-align">
                                {{ tag.count }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="bottom-section">
                <h2 class="section-title">Artist</h2>
                <table class="data-table">
                    <colgroup>
                        <col class="tag-col">
                        <col class="count-col">
                    </colgroup>
                    <thead>
                        <tr>
                            <th class="left-align">Tag</th>
                            <th class="right-align">Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="tag in tags.artist" :key="tag.tag" v-tooltip.bottom="[
                            `${tag.tag}`,
                            `翻译: ${tag.tag_cn || 'N/A'}`,
                            tag.intro ? `介绍: ${tag.intro.length > 100 ? tag.intro.slice(0, 100) + '...' : tag.intro}` : null
                        ].filter(Boolean).join('\n')">
                            <td class="left-align">
                                {{ tag.tag_cn || tag.tag.replace(/^artist:/, '') }}
                            </td>
                            <td class="right-align">{{ tag.count }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="bottom-section">
                <h2 class="section-title">Parody</h2>
                <table class="data-table">
                    <colgroup>
                        <col class="tag-col">
                        <col class="count-col">
                    </colgroup>
                    <thead>
                        <tr>
                            <th class="left-align">Tag</th>
                            <th class="right-align">Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="tag in tags.parody" :key="tag.tag" v-tooltip.bottom="[
                            `${tag.tag}`,
                            `翻译: ${tag.tag_cn || 'N/A'}`,
                            tag.intro ? `介绍: ${tag.intro.length > 100 ? tag.intro.slice(0, 100) + '...' : tag.intro}` : null
                        ].filter(Boolean).join('\n')">
                            <td class="left-align">
                                {{ tag.tag_cn || tag.tag.replace(/^parody:/, '') }}
                            </td>
                            <td class="right-align">{{ tag.count }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="bottom-section">
                <h2 class="section-title">Character</h2>
                <table class="data-table">
                    <colgroup>
                        <col class="tag-col">
                        <col class="count-col">
                    </colgroup>
                    <thead>
                        <tr>
                            <th class="left-align">Tag</th>
                            <th class="right-align">Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="tag in tags.character" :key="tag.tag" v-tooltip.bottom="[
                            `${tag.tag}`,
                            `翻译: ${tag.tag_cn || 'N/A'}`,
                            tag.intro ? `介绍: ${tag.intro.length > 100 ? tag.intro.slice(0, 100) + '...' : tag.intro}` : null
                        ].filter(Boolean).join('\n')">
                            <td class="left-align">
                                {{ tag.tag_cn || tag.tag.replace(/^character:/, '') }}
                            </td>
                            <td class="right-align">{{ tag.count }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>
</template>

<script>
import { ref, onMounted, watch } from "vue";
import Chart from "primevue/chart";
import ToggleSwitch from "primevue/toggleswitch";
import { useTheme } from '@/composables/useTheme';
import '@/assets/DataAnalys.css';
import { Chart as ChartJS } from 'chart.js';
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix';

// 注册 matrix 图表类型
ChartJS.register(MatrixController, MatrixElement);

const baseUrl = import.meta.env.BASE_URL;
export default {
    components: { Chart, ToggleSwitch },
    setup() {
        const { isDark } = useTheme()
        return { isDark }
    },
    data() {
        return {
            stats: {
                total_count: 0,
                categories: {},
            },
            tags: {
                artist: [],
                other: [],
                female: [],
                male: [],
                character: [],
                parody: []
            },
            types: ["artist", "other", "female", "male", "character", "parody"],
            chartData: null,
            chartOptions: null,
            femaleChartData: null,
            maleChartData: null,
            barChartOptions: null,
            categoryColors: {
                Doujinshi: "#a11",
                Manga: "#d67e22",
                "Artist CG": "#d6a922",
                "Game CG": "#4caf50",
                Western: "#d4af37",
                "Non-H": "#4ca3dd",
                "Image Set": "#2a78d6",
                Cosplay: "#7e57c2",
                "Asian Porn": "#a11548",
                Misc: "#757575",
            },
            // 新增用于季度折线图的数据和选项
            quarterlyLineData: null,
            quarterlyLineOptions: null,
            // 热力图数据
            heatmapChartData: null,
            heatmapChartOptions: null,
            // 完整季度数据
            fullQuarterlyData: [],
            showFullData: false,
        };
    },
    mounted() {
        this.fetchPrecomputedStats();
    },
    watch: {
        isDark: {
            handler() {
                // 主题切换时重新生成图表配置
                this.updateChart();
                this.updateBarCharts();
                if (this.fullQuarterlyData && this.fullQuarterlyData.length > 0) {
                    // 重新创建季度图表
                    this.updateQuarterlyChart();
                }
                // 重新生成热力图（使用已加载的数据）
                if (this.heatmapChartData && this.heatmapChartData.datasets && this.heatmapChartData.datasets[0]) {
                    // 从已有数据中提取并重新渲染
                    const matrixData = this.heatmapChartData.datasets[0].data;
                    const values = matrixData.map(d => d.v).filter(v => v > 0);
                    const maxValue = Math.max(...values, 1);
                    this.initHeatmapFromPrecomputed({ data: matrixData, maxValue });
                }
            },
            immediate: false
        }
    },
    methods: {
        async fetchPrecomputedStats() {
            try {
                // 读取预计算的统计数据
                const response = await fetch(`${baseUrl}data/stats.json`);
                const precomputed = await response.json();

                // 加载基础统计
                this.stats = precomputed.stats;
                this.updateChart();

                // 加载标签统计
                this.tags = precomputed.tags;
                this.updateBarCharts();

                // 加载季度数据
                this.fullQuarterlyData = precomputed.quarterly;
                this.updateQuarterlyChart();

                // 加载热力图数据
                this.initHeatmapFromPrecomputed(precomputed.heatmap);
            } catch (error) {
                console.error("Failed to fetch precomputed stats:", error);
            }
        },
        updateQuarterlyChart() {
            let data = this.fullQuarterlyData;
            let displayData = data;

            if (!this.showFullData && data.length > 0) {
                // 计算5年前的季度
                const currentDate = new Date();
                const currentYear = currentDate.getFullYear();
                const currentMonth = currentDate.getMonth() + 1;
                const currentQuarter = Math.ceil(currentMonth / 3);

                const fiveYearsAgo = currentYear - 5;
                const cutoffQuarter = `${fiveYearsAgo}-Q${currentQuarter}`;

                // 过滤出近5年的数据
                displayData = data.filter(item => item.quarter >= cutoffQuarter);
            }

            this.initQuarterlyLineChart(displayData);
        },
        toggleFullData() {
            this.updateQuarterlyChart();
        },
        updateChart() {
            const labels = Object.keys(this.stats.categories);
            const data = Object.values(this.stats.categories);
            const backgroundColors = labels.map(
                (label) => this.categoryColors[label] || "#757575"
            );

            this.chartData = {
                labels,
                datasets: [
                    {
                        data,
                        backgroundColor: backgroundColors,
                    },
                ],
            };
            this.chartOptions = this.getChartOptions();
        },
        updateBarCharts() {
            // Female Chart Data
            const femaleLabels = this.tags.female.map((tag) => tag.tag_cn || tag.tag.replace(/^female:/, '')); // 默认显示中文
            const femaleCounts = this.tags.female.map((tag) => tag.count);
            this.femaleChartData = {
                labels: femaleLabels,
                datasets: [
                    {
                        label: "Female Tags",
                        data: femaleCounts,
                        backgroundColor: "#f06292",
                    },
                ],
            };

            // Male Chart Data
            const maleLabels = this.tags.male.map((tag) => tag.tag_cn || tag.tag.replace(/^male:/, '')); // 默认显示中文
            const maleCounts = this.tags.male.map((tag) => tag.count);
            this.maleChartData = {
                labels: maleLabels,
                datasets: [
                    {
                        label: "Male Tags",
                        data: maleCounts,
                        backgroundColor: "#42a5f5",
                    },
                ],
            };

            this.barChartOptions = this.getBarChartOptions();
        },
        initQuarterlyLineChart(quarterlyData) {
            // quarterlyData 格式： [{ "quarter": "2022-Q1", "postedCount": 123, "favTimeCount": 45 }, ...]
            const quarters = quarterlyData.map(item => item.quarter);
            const postedCounts = quarterlyData.map(item => item.postedCount);
            const favTimeCounts = quarterlyData.map(item => item.favTimeCount);

            // 动态主题颜色
            const textColor = this.isDark ? '#f1f5f9' : '#2d3748';
            const textColorSecondary = this.isDark ? '#cbd5e1' : '#64748b';
            const gridColor = this.isDark ? '#475569' : '#d6d3d1';

            // Posted 线条颜色
            const postedBorderColor = this.isDark ? '#00bcd4' : '#0891b2';
            const postedBgColor = this.isDark ? 'rgba(0, 188, 212, 0.2)' : 'rgba(8, 145, 178, 0.1)';

            // FavTime 线条颜色
            const favTimeBorderColor = this.isDark ? '#f06292' : '#e91e63';
            const favTimeBgColor = this.isDark ? 'rgba(240, 98, 146, 0.2)' : 'rgba(233, 30, 99, 0.1)';

            this.quarterlyLineData = {
                labels: quarters,
                datasets: [
                    {
                        label: 'Posted Time',
                        data: postedCounts,
                        fill: true,
                        borderColor: postedBorderColor,
                        tension: 0.4,
                        backgroundColor: postedBgColor
                    },
                    {
                        label: 'Favorite Time',
                        data: favTimeCounts,
                        fill: true,
                        borderColor: favTimeBorderColor,
                        tension: 0.4,
                        backgroundColor: favTimeBgColor
                    }
                ]
            };

            this.quarterlyLineOptions = {
                maintainAspectRatio: false,
                aspectRatio: 0.6,
                plugins: {
                    legend: {
                        labels: {
                            color: textColor
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: textColorSecondary
                        },
                        grid: {
                            color: gridColor
                        }
                    },
                    y: {
                        ticks: {
                            color: textColorSecondary
                        },
                        grid: {
                            color: gridColor
                        }
                    }
                }
            };
        },
        getChartOptions() {
            // 动态主题颜色
            const textColor = this.isDark ? '#f1f5f9' : '#2d3748';
            const gridColor = this.isDark ? '#475569' : '#d6d3d1';
            
            return {
                plugins: {
                    legend: {
                        labels: {
                            usePointStyle: true,
                            color: textColor,
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            color: textColor,
                        },
                        grid: {
                            color: gridColor,
                        },
                    },
                    y: {
                        ticks: {
                            color: textColor,
                            beginAtZero: true,
                        },
                        grid: {
                            color: gridColor,
                        },
                    },
                },
            };
        },
        getBarChartOptions() {
            // 动态主题颜色
            const textColor = this.isDark ? '#f1f5f9' : '#2d3748';
            const gridColor = this.isDark ? '#475569' : '#d6d3d1';
            
            return {
                plugins: {
                    legend: {
                        labels: {
                            color: textColor,
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            color: textColor,
                            font: {
                                size: 12,
                            },
                        },
                        grid: {
                            color: gridColor,
                        },
                    },
                    y: {
                        ticks: {
                            color: textColor,
                            font: {
                                size: 12,
                            },
                            beginAtZero: true,
                        },
                        grid: {
                            color: gridColor,
                        },
                    },
                },
            };
        },
        initHeatmapFromPrecomputed(heatmapData) {
            try {
                const matrixData = heatmapData.data;
                const maxValue = heatmapData.maxValue;

                // 配置图表
                const textColor = this.isDark ? '#f1f5f9' : '#2d3748';
                const gridColor = this.isDark ? '#475569' : '#d6d3d1';
                const isDarkMode = this.isDark;

                this.heatmapChartData = {
                    datasets: [{
                        label: 'Favorites Added',
                        data: matrixData,
                        backgroundColor: (context) => {
                            const value = context.dataset.data[context.dataIndex].v;
                            if (value === 0) return isDarkMode ? '#1e293b' : '#ebedf0';

                            const alpha = Math.min(value / maxValue, 1);
                            if (alpha <= 0.25) return isDarkMode ? '#0e4429' : '#9be9a8';
                            if (alpha <= 0.5) return isDarkMode ? '#006d32' : '#40c463';
                            if (alpha <= 0.75) return isDarkMode ? '#26a641' : '#30a14e';
                            return isDarkMode ? '#39d353' : '#216e39';
                        },
                        borderColor: gridColor,
                        borderWidth: 1,
                        width: 15,
                        height: 15,
                    }]
                };

                this.heatmapChartOptions = {
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title() { return ''; },
                                label(context) {
                                    const item = context.dataset.data[context.dataIndex];
                                    return `${item.d}: ${item.v} favorites`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            offset: false,
                            display: false
                        },
                        y: {
                            type: 'linear',
                            offset: false,
                            reverse: true,
                            ticks: {
                                stepSize: 1,
                                color: textColor,
                                callback: function(value) {
                                    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
                                    return days[value] || '';
                                }
                            },
                            grid: { display: false }
                        }
                    }
                };
            } catch (error) {
                console.error("Failed to init heatmap from precomputed:", error);
            }
        },
    },
};
</script>