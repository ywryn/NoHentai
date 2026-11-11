<template>
    <div class="data-container">
        <div class="data-page-header">
            <div class="page-copy">
                <h1 class="page-title">收藏统计</h1>

            </div>
            <div class="insight-strip" aria-label="收藏概览">
                <div><strong>{{ statsLoaded ? stats.total_count.toLocaleString() : '—' }}</strong><span>总收录</span></div>
                <div><strong>{{ statsLoaded ? recentActivity.count : '—' }}</strong><span>近 30 天新增</span></div>
                <div><strong>{{ statsLoaded ? recentActivity.activeDays : '—' }}</strong><span>近 30 天活跃天数</span></div>
            </div>
        </div>

        <div v-if="statsError" class="stats-load-error" role="alert"><span>{{statsError}}</span><button type="button" @click="fetchStats">重新加载</button></div>
        <div v-if="loadingStats && !statsLoaded" class="stats-loading" role="status" aria-live="polite">
            <div class="stats-loading-line"></div><div class="stats-loading-line short"></div>
            <span>正在加载统计数据…</span>
        </div>
        <template v-if="statsLoaded">
        <section class="data-panel heatmap-section">
            <div class="panel-header">
                <div>
                    <h2 class="section-title">收藏热力图</h2>
                </div>
            </div>
            <div class="heatmap-chart-container">
                <Chart type="matrix" :data="heatmapChartData" :options="heatmapChartOptions" class="heatmap-chart" />
            </div>
        </section>

        <div class="stats-row">
            <section class="data-panel stats-left">
                <div class="panel-header panel-header-spread">
                    <div>
                        <h2 class="section-title-large">季度增长</h2>
                    </div>
                    <div class="toggle-wrapper">
                        <span class="toggle-label">显示全部年份</span>
                        <ToggleSwitch v-model="showFullData" @change="toggleFullData" />
                    </div>
                </div>

                <div class="line-chart-container">
                    <Chart type="line" :data="quarterlyLineData" :options="quarterlyLineOptions" class="chart-full" />
                </div>
            </section>
            <section class="data-panel stats-right">
                <div class="panel-header">
                    <div>
                        <h2 class="section-title">分类分布</h2>
                    </div>
                </div>
                <div class="category-list" role="list" aria-label="按数量排序的分类">
                    <div v-for="category in sortedCategories" :key="category.name" class="category-item" role="listitem">
                        <div class="category-meta"><span>{{ category.name }}</span><strong>{{ category.count.toLocaleString() }}</strong></div>
                        <div class="category-track"><div :style="{ width: `${category.share}%` }"></div></div>
                    </div>
                    <p v-if="!sortedCategories.length" class="stats-empty">暂无分类数据</p>
                </div>
            </section>
        </div>

        <div class="tags-row">
            <TagCountTable namespace="female" title="Female 标签排行" :rows="tags.female" :initial-count="10" />
            <TagCountTable namespace="male" title="Male 标签排行" :rows="tags.male" :initial-count="10" />
        </div>

        <div class="tag-namespace-tabs" aria-label="标签排行类别">
            <button v-for="tab in tagNamespaceTabs" :key="tab.key" type="button" :aria-pressed="selectedNamespace === tab.key" @click="selectedNamespace = tab.key">{{ tab.label }}</button>
        </div>
        <div class="bottom-row">
            <TagCountTable v-for="tab in tagNamespaceTabs" :key="tab.key" :class="{'tag-table-mobile-hidden':selectedNamespace !== tab.key}" :namespace="tab.key" :title="tab.label" :rows="tags[tab.key]" />
        </div>
        </template>
    </div>
</template>

<script>
import Chart from "primevue/chart";
import TagCountTable from "@/components/TagCountTable.vue";
import ToggleSwitch from "primevue/toggleswitch";
import { useTheme } from '@/composables/useTheme';
import '@/assets/DataAnalys.css';
import { Chart as ChartJS } from 'chart.js';
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix';

// 注册 matrix 图表类型
ChartJS.register(MatrixController, MatrixElement);

export default {
    components: { Chart, ToggleSwitch, TagCountTable },
    setup() {
        const { isDark } = useTheme()
        return { isDark }
    },
    data() {
        return {
            loadingStats: false,
            statsLoaded: false,
            statsError: "",
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
            tagNamespaceTabs: [{key:'other',label:'Other'},{key:'artist',label:'Artist'},{key:'parody',label:'Parody'},{key:'character',label:'Character'}],
            selectedNamespace: 'other',
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
        this.fetchStats();
        window.addEventListener("focus",this.refreshVisibleStats);
        document.addEventListener("visibilitychange",this.refreshVisibleStats);
    },
    beforeUnmount() {
        this._statsController?.abort();
        window.removeEventListener("focus",this.refreshVisibleStats);
        document.removeEventListener("visibilitychange",this.refreshVisibleStats);
    },
    computed: {
        sortedCategories() {
            const total = Number(this.stats.total_count) || 0;
            return Object.entries(this.stats.categories || {})
                .map(([name, value]) => ({name, count: Number(value) || 0}))
                .filter(item => item.count > 0)
                .sort((a, b) => b.count - a.count)
                .map(item => ({...item, share: total ? Math.min(100, item.count / total * 100) : 0}));
        },
        recentActivity() {
            const rows = this.heatmapChartData?.datasets?.[0]?.data || [];
            const cutoff = new Date();
            cutoff.setUTCDate(cutoff.getUTCDate() - 29);
            const day = cutoff.toISOString().slice(0, 10);
            const recent = rows.filter(row => row.d >= day);
            return {count: recent.reduce((sum, row) => sum + (Number(row.v) || 0), 0), activeDays: recent.filter(row => row.v > 0).length};
        },
    },
    watch: {
        isDark: {
            handler() {
                // 主题切换时重新生成图表配置
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
        refreshVisibleStats() { if(document.visibilityState==='visible')this.fetchStats(); },
        async fetchStats() {
            if(this.loadingStats)return;
            this.loadingStats=true;this.statsError='';
            const controller=new AbortController();this._statsController=controller;
            try {
                const response = await fetch('/api/stats',{signal:controller.signal,cache:'no-store'});
                if(!response.ok)throw new Error('统计加载失败（HTTP '+response.status+'）');
                const precomputed = await response.json();

                // 加载基础统计
                this.stats = precomputed.stats;

                // 加载标签统计
                this.tags = precomputed.tags;

                // 加载季度数据
                this.fullQuarterlyData = precomputed.quarterly;
                this.updateQuarterlyChart();

                // 加载热力图数据
                this.initHeatmapFromPrecomputed(precomputed.heatmap);
                this.statsLoaded=true;
            } catch (error) {
                if(error.name!=='AbortError')this.statsError=error.message||'统计加载失败，请重试';
            } finally {this.loadingStats=false;}
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
