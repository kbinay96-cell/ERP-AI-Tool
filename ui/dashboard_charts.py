# ui/dashboard_charts.py
#
# Converted to PyQt6 (was PySide6) so it matches the rest of the app.
#
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCharts import QChart, QChartView, QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt


class InventoryChartWidget(QWidget):
    """Warehouse Inventory Levels vs Reorder Points Chart"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.chart = QChart()
        self.chart.setTitle("Warehouse Stock Levels vs Reorder Point (ROP)")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.layout.addWidget(self.chart_view)

    def update_chart(self, warehouse_data: list):
        # Clear existing series & axes safely
        for s in list(self.chart.series()):
            self.chart.removeSeries(s)
        for axis in list(self.chart.axes()):
            try:
                self.chart.removeAxis(axis)
            except Exception:
                pass

        set_stock = QBarSet("Stock on Hand")
        set_rop = QBarSet("Reorder Point (ROP)")
        
        set_stock.setColor(QColor("#2b5c8f"))
        set_rop.setColor(QColor("#d9534f"))

        categories = []
        max_val = 0

        for wh in warehouse_data:
            categories.append(wh.get("wh_id", "Unknown"))
            stock = wh.get("stock_on_hand", 0)
            rop = wh.get("reorder_point", 0)
            
            set_stock.append(stock)
            set_rop.append(rop)
            max_val = max(max_val, stock, rop)

        series = QBarSeries()
        series.append(set_stock)
        series.append(set_rop)

        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, max_val + 50 if max_val is not None else 100)
        axis_y.setTitleText("Units")
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)


class ProductionBottleneckChartWidget(QWidget):
    """Work Center Hours & Bottleneck Visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self.chart = QChart()
        self.chart.setTitle("Work Center Processing Hours")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.layout.addWidget(self.chart_view)

    def update_chart(self, route_data: list):
        for s in list(self.chart.series()):
            self.chart.removeSeries(s)
        for axis in list(self.chart.axes()):
            try:
                self.chart.removeAxis(axis)
            except Exception:
                pass

        set_hours = QBarSet("Processing Time (Hours)")
        set_hours.setColor(QColor("#f0ad4e"))

        categories = []
        max_hours = 0

        for step in route_data:
            wc_id = step.get("center_id", "WC")
            hours = step.get("process_time_hours", 0)
            categories.append(wc_id)
            set_hours.append(hours)
            max_hours = max(max_hours, hours)

        series = QBarSeries()
        series.append(set_hours)

        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, max_hours + 5 if max_hours is not None else 10)
        axis_y.setTitleText("Hours")
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)