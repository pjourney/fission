# SPDX-License-Identifier: MIT
"""Generate a small reviewable source patch without changing the baseline tree.

The navigation implementation is adapted from the pinned upstream CAD preset;
its original license/copyright header is preserved, as are its SpaceMouse hooks.
"""
from pathlib import Path
import difflib
import json
import subprocess

root = Path(__file__).resolve().parents[1]
source = root / "upstream-src"
changes = {}
revision = json.loads((root / "source-lock.json").read_text(encoding="utf-8"))["revision"]


def baseline(relative):
    return subprocess.check_output(["git", "-C", str(source), "show", revision + ":" + relative]).decode("utf-8").replace("\r\n", "\n")


def replace_file(relative, pairs):
    original = baseline(relative)
    revised = original
    for before, after in pairs:
        if before not in revised:
            raise RuntimeError("Pinned source context changed: " + relative + " / " + before[:70])
        revised = revised.replace(before, after, 1)
    changes[relative] = (original, revised)


replace_file("src/Main/MainGui.cpp", [
    ('Config()["ExeName"] = "FreeCAD"', 'Config()["ExeName"] = "Fission"'),
    ('Config()["ExeVendor"] = "FreeCAD"', 'Config()["ExeVendor"] = "Fission"'),
    ('Config()["AppIcon"] = "freecad"', 'Config()["AppIcon"] = "fission"'),
    ('Config()["SplashScreen"] = "freecadsplash"', 'Config()["SplashScreen"] = "fissionsplash"'),
    ('Config()["StartWorkbench"] = "PartDesignWorkbench"',
     'Config()["StartWorkbench"] = "FissionWorkbench";\n    App::Application::Config()["NavigationStyle"] = "Gui::FissionNavigationStyle"'),
    ('Config()["DesktopFileName"] = "org.freecad.FreeCAD"', 'Config()["DesktopFileName"] = "org.fission.Fission"'),
    ('        Gui::Application::initApplication();', '''        // Fission uses stable Qt docks around its unified canvas. Configure
        // this before the native dock manager constructs overlay containers.
        auto shellPreferences = App::GetApplication().GetUserParameter()
            .GetGroup("BaseApp/Preferences/Fission");
        if (shellPreferences->GetInt("DockingVersion", 0) < 1) {
            App::GetApplication().GetUserParameter()
                .GetGroup("BaseApp/Preferences/DockWindows")
                ->SetBool("ActivateOverlay", false);
            for (const char* side : {"OverlayLeft", "OverlayRight", "OverlayTop", "OverlayBottom"}) {
                App::GetApplication().GetUserParameter()
                    .GetGroup("BaseApp/MainWindow/DockWindows")->GetGroup(side)
                    ->SetASCII("Widgets", "");
            }
            shellPreferences->SetInt("DockingVersion", 1);
        }
        Gui::Application::initApplication();'''),
])
replace_file("src/Main/MainCmd.cpp", [
    ('Config()["ExeName"] = "FreeCAD"', 'Config()["ExeName"] = "Fission"'),
    ('Config()["ExeVendor"] = "FreeCAD"', 'Config()["ExeVendor"] = "Fission"'),
])
replace_file("src/Main/CMakeLists.txt", [
    ('SET_BIN_DIR(FreeCADMain FreeCAD)', 'SET_BIN_DIR(FreeCADMain Fission)'),
    ('SET_BIN_DIR(FreeCADMainCmd FreeCADCmd)', 'SET_BIN_DIR(FreeCADMainCmd FissionCmd)'),
])
for filename, executable in [("freecad.rc.cmake", "Fission.exe"), ("freecadCmd.rc.cmake", "FissionCmd.exe")]:
    replace_file("src/Main/" + filename, [
        ('"${PROJECT_NAME} Team"', '"Fission contributors"'),
        ('"${PROJECT_NAME} main executable"', '"Fission parametric mechanical CAD"') if filename == "freecad.rc.cmake"
        else ('"${PROJECT_NAME} command line executable"', '"Fission CAD command line"'),
        ('"FreeCAD.exe"' if filename == "freecad.rc.cmake" else '"FreeCADCmd.exe"', '"' + executable + '"'),
        ('"FreeCAD.exe"' if filename == "freecad.rc.cmake" else '"FreeCADCmd.exe"', '"' + executable + '"'),
        ('"${PROJECT_NAME}"', '"Fission"'),
    ])
replace_file("src/Gui/Icons/resource.qrc", [
    ('<file>freecadsplash.svg</file>', '<file>freecadsplash.svg</file>\n        <file>fission.svg</file>\n        <file>fissionsplash.svg</file>'),
])
replace_file("src/Gui/CMakeLists.txt", [
    ('Navigation/CADNavigationStyle.cpp', 'Navigation/CADNavigationStyle.cpp\n    Navigation/FissionNavigationStyle.cpp'),
])
replace_file("src/Gui/SoFCDB.cpp", [
    ('CADNavigationStyle::init();', 'CADNavigationStyle::init();\n    FissionNavigationStyle::init();'),
])
declaration = '''class GuiExport FissionNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;
    TYPESYSTEM_HEADER_WITH_OVERRIDE();
public:
    FissionNavigationStyle();
    ~FissionNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;
    std::string userFriendlyName() const override { return "Fission / Fusion"; }
protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
private:
    SbBool lockButton1 {false};
};

'''
replace_file("src/Gui/Navigation/NavigationStyle.h", [
    ('class GuiExport RevitNavigationStyle:', declaration + 'class GuiExport RevitNavigationStyle:'),
    ('''        Clip = 4,       /**< Clip objects using a lasso. */
    };
''', '''        Clip = 4,       /**< Clip objects using a lasso. */
        Freehand = 5,   /**< Select objects using a dragged freehand outline. */
    };
'''),
])
replace_file("src/Mod/Sketcher/Gui/ViewProviderSketch.cpp", [
    ('"if ActiveSketch.ViewObject.EditingWorkbench:\\n"',
     '"if ActiveSketch.ViewObject.EditingWorkbench and Gui.activeWorkbench().name() != \'FissionWorkbench\':\\n"'),
])

# Native feature editors can construct their panels before the editing view
# becomes active. Bind them to the feature's document rather than whichever
# document a workbench transition happens to activate at that instant.
feature_workbench = '''auto* activeWorkbench = Gui::WorkbenchManager::instance()->active();
        oldWb = activeWorkbench && activeWorkbench->name() == "FissionWorkbench"
            ? "FissionWorkbench"
            : Gui::Command::assureWorkbench("PartDesignWorkbench");'''
for filename in ("ViewProvider.cpp", "ViewProviderDatum.cpp"):
    pairs = [
        ('#include <Gui/MainWindow.h>', '#include <Gui/MainWindow.h>\n#include <Gui/Workbench.h>\n#include <Gui/WorkbenchManager.h>'),
        ('Gui::Control().activeDialog();', 'Gui::Control().activeDialog(getObject()->getDocument());'),
        ('oldWb = Gui::Command::assureWorkbench("PartDesignWorkbench");', feature_workbench),
    ]
    if filename == "ViewProvider.cpp":
        pairs += [
            ('// always change to PartDesign WB, remember where we come from', '// Keep the unified Fission workspace while using native feature editors.'),
            ('Gui::Control().reject();', 'Gui::Control().reject(getObject()->getDocument());'),
            ('Gui::Control().showDialog(featureDlg);', 'Gui::Control().showDialog(featureDlg, getObject()->getDocument());'),
            ('Gui::Control().closeDialog();', 'Gui::Control().closeDialog(getObject()->getDocument());'),
        ]
    else:
        pairs += [
            ('Gui::Control().closeDialog();', 'Gui::Control().closeDialog(getObject()->getDocument());'),
            ('Gui::Control().closeDialog();', 'Gui::Control().closeDialog(getObject()->getDocument());'),
            ('Gui::Control().showDialog(datumDlg);', 'Gui::Control().showDialog(datumDlg, getObject()->getDocument());'),
            ('Gui::Control().showDialog(new TaskDlgDatumParameters(this));', 'Gui::Control().showDialog(new TaskDlgDatumParameters(this), getObject()->getDocument());'),
        ]
    replace_file("src/Mod/PartDesign/Gui/" + filename, pairs)

# Keep native Assembly edit mode and its solver panel within the unified shell.
replace_file("src/Mod/Assembly/Gui/ViewProviderAssembly.cpp", [
    ('#include <Gui/MainWindow.h>', '#include <Gui/MainWindow.h>\n#include <Gui/Workbench.h>\n#include <Gui/WorkbenchManager.h>'),
    ('        // assure the Assembly workbench\n        if (App::GetApplication()',
     '''        // Preserve the unified shell while using native Assembly editing.
        auto* activeWorkbench = Gui::WorkbenchManager::instance()->active();
        const bool isFissionWb = activeWorkbench && activeWorkbench->name() == "FissionWorkbench";
        if (!isFissionWb && App::GetApplication()'''),
    ('bool isAssemblyWb = (name == QLatin1String("AssemblyWorkbench"));',
     'bool isAssemblyWb = (name == QLatin1String("AssemblyWorkbench")\n                         || name == QLatin1String("FissionWorkbench"));'),
])

# Assembly's Python wrapper must inherit the native document-provider API.
replace_file("src/Mod/Assembly/Gui/ViewProviderAssembly.pyi", [
    ('from Gui.ViewProvider import ViewProvider',
     'from Gui.ViewProviderGeometryObject import ViewProviderGeometryObject'),
    ('class ViewProviderAssembly(ViewProvider):',
     'class ViewProviderAssembly(ViewProviderGeometryObject):'),
])
replace_file("src/Mod/Assembly/Gui/AppAssemblyGui.cpp", [
    ('#include "ViewProviderAssembly.h"', '#include "ViewProviderAssembly.h"\n#include "ViewProviderAssemblyPy.h"'),
    ('    AssemblyGui::ViewProviderSnapshotGroup::init();\n',
     '''    AssemblyGui::ViewProviderSnapshotGroup::init();

    Base::Interpreter().addType(
        &AssemblyGui::ViewProviderAssemblyPy::Type,
        mod,
        "ViewProviderAssembly"
    );
'''),
])

# GUI observers must not cache base-class Python bindings during construction.
replace_file("src/Gui/DocumentObserverPython.cpp", [
    ('''void DocumentObserverPython::slotBeforeChangeObject(
    const Gui::ViewProvider& Obj,
    const App::Property& Prop
)
{
''', '''void DocumentObserverPython::slotBeforeChangeObject(
    const Gui::ViewProvider& Obj,
    const App::Property& Prop
)
{
    // Base constructors change properties before the provider is attached.
    // Requesting a Python object there caches an incomplete base-class binding.
    const auto* provider = dynamic_cast<const Gui::ViewProviderDocumentObject*>(&Obj);
    if (provider && !provider->getObject()) {
        return;
    }

'''),
    ('void DocumentObserverPython::slotChangedObject(const Gui::ViewProvider& Obj, const App::Property& Prop)\n{\n',
     '''void DocumentObserverPython::slotChangedObject(const Gui::ViewProvider& Obj, const App::Property& Prop)
{
    // Base constructors change properties before the provider is attached.
    // Requesting a Python object there caches an incomplete base-class binding.
    const auto* provider = dynamic_cast<const Gui::ViewProviderDocumentObject*>(&Obj);
    if (provider && !provider->getObject()) {
        return;
    }

'''),
])

navigation = baseline("src/Gui/Navigation/CADNavigationStyle.cpp")
navigation = navigation.replace("CADNavigationStyle", "FissionNavigationStyle")
navigation = navigation.replace('QT_TR_NOOP("Press middle or ctrl+right mouse button")', 'QT_TR_NOOP("Hold middle mouse button and drag")')
navigation = navigation.replace('QT_TR_NOOP("Press middle+left, middle+right or shift+right mouse button")', 'QT_TR_NOOP("Hold Shift and middle mouse button and drag")')
navigation = navigation.replace('"Scroll mouse wheel or keep middle button depressed\\n"\n                "while doing a left or right click and move the mouse up or down"',
                                '"Scroll mouse wheel or hold Ctrl+Shift and middle mouse button and drag"')
anchor = "        case CTRLDOWN | BUTTON2DOWN:\n"
new_cases = '''        // Fission factory preset: Autodesk's public default mouse gestures.
        // Preserve upstream camera math, selection, editing and 3Dconnexion paths.
        case SHIFTDOWN | BUTTON3DOWN:
            if (newmode != NavigationStyle::DRAGGING) {
                saveCursorPosition(ev);
            }
            newmode = NavigationStyle::DRAGGING;
            break;
        case CTRLDOWN | SHIFTDOWN | BUTTON3DOWN:
            newmode = NavigationStyle::ZOOMING;
            break;
'''
assert anchor in navigation
navigation = navigation.replace(anchor, new_cases + anchor, 1)
changes["src/Gui/Navigation/FissionNavigationStyle.cpp"] = ("", navigation)
for filename in ("fission.svg", "fissionsplash.svg"):
    changes["src/Gui/Icons/" + filename] = ("", (root / "Mod/Fission/resources" / filename).read_text(encoding="utf-8"))

# Preserve document-owned contextual panels across operation dialogs.
replace_file("src/Gui/TaskView/TaskView.cpp", [
    ('''}

void TaskView::slotActiveDocument(const App::Document& doc)
{
    auto foundTaskInfo = std::ranges::find(taskInfos, &doc, &TaskInfo::Document);
    if (foundTaskInfo != taskInfos.end()) {
        setShownTaskInfo((foundTaskInfo - taskInfos.begin()));
    }
''', '''}

void TaskView::slotActiveDocument(const App::Document& doc)
{
    for (QWidget* panel : TaskWatcherPanel->contextualPanels) {
        const QVariant owner = panel->property("contextualDocument");
        if (owner.isValid()) {
            panel->setVisible(owner.toString() == QString::fromUtf8(doc.getName()));
        }
    }
    auto foundTaskInfo = std::ranges::find(taskInfos, &doc, &TaskInfo::Document);
    if (foundTaskInfo != taskInfos.end()) {
        setShownTaskInfo((foundTaskInfo - taskInfos.begin()));
    }
'''),
    ('''
    if (remove) {
        remove->ActiveDialog->closed();
        remove->ActiveDialog->emitDestructionSignal();
        delete remove->ActiveCtrl;
        delete remove->ActiveDialog;
        delete remove->taskPanel;
    }
''', '''
    if (remove) {
        remove->ActiveDialog->closed();
        remove->ActiveDialog->emitDestructionSignal();
        // Contextual solver panels belong to their document, not to the
        // temporary operation dialog. Keep them alive after its OK/Cancel.
        const auto panels = remove->taskPanel->contextualPanels;
        remove->taskPanel->contextualPanels.clear();
        for (QWidget* panel : panels) {
            remove->taskPanel->contextualPanelsLayout->removeWidget(panel);
            addContextualPanel(panel, remove->Document);
        }
        delete remove->ActiveCtrl;
        delete remove->ActiveDialog;
        delete remove->taskPanel;
    }
'''),
    ('''
void TaskView::addContextualPanel(QWidget* panel, App::Document* doc)
{
    auto foundTaskInfo = std::ranges::find(taskInfos, doc, &TaskInfo::Document);
    if (!panel || foundTaskInfo == taskInfos.end()
        || foundTaskInfo->taskPanel->contextualPanels.contains(panel)) {
        return;
    }

    foundTaskInfo->taskPanel->contextualPanelsLayout->addWidget(panel);
    foundTaskInfo->taskPanel->contextualPanels.append(panel);
    panel->show();
    triggerMinimumSizeHint();
    Q_EMIT taskUpdate();
}

void TaskView::removeContextualPanel(QWidget* panel, App::Document* doc)
{
    auto foundTaskInfo = std::ranges::find(taskInfos, doc, &TaskInfo::Document);
    if (!panel || foundTaskInfo == taskInfos.end()
        || !foundTaskInfo->taskPanel->contextualPanels.contains(panel)) {
        return;
    }


    foundTaskInfo->taskPanel->contextualPanelsLayout->removeWidget(panel);
    foundTaskInfo->taskPanel->contextualPanels.removeOne(panel);
    panel->deleteLater();
    triggerMinimumSizeHint();
    Q_EMIT taskUpdate();
}
''', '''
void TaskView::addContextualPanel(QWidget* panel, App::Document* doc)
{
    auto foundTaskInfo = std::ranges::find(taskInfos, doc, &TaskInfo::Document);
    TaskPanel* target = foundTaskInfo == taskInfos.end() ? TaskWatcherPanel : foundTaskInfo->taskPanel;
    if (!panel || target->contextualPanels.contains(panel)) {
        return;
    }

    if (doc) {
        panel->setProperty("contextualDocument", QString::fromUtf8(doc->getName()));
    }
    target->contextualPanelsLayout->addWidget(panel);
    target->contextualPanels.append(panel);
    // A stacked task panel controls its children's document visibility.
    // Only the shared watcher panel needs to filter individual children.
    panel->setVisible(
        target != TaskWatcherPanel || !doc || doc == App::GetApplication().getActiveDocument()
    );
    triggerMinimumSizeHint();
    Q_EMIT taskUpdate();
}

void TaskView::removeContextualPanel(QWidget* panel, App::Document* doc)
{
    auto foundTaskInfo = std::ranges::find(taskInfos, doc, &TaskInfo::Document);
    TaskPanel* target = foundTaskInfo == taskInfos.end() ? TaskWatcherPanel : foundTaskInfo->taskPanel;
    if (panel && !target->contextualPanels.contains(panel) && TaskWatcherPanel->contextualPanels.contains(panel)) {
        target = TaskWatcherPanel;
    }
    if (!panel || !target->contextualPanels.contains(panel)) {
        return;
    }


    target->contextualPanelsLayout->removeWidget(panel);
    target->contextualPanels.removeOne(panel);
    panel->hide();
    panel->deleteLater();
    triggerMinimumSizeHint();
    Q_EMIT taskUpdate();
}
'''),
])

# Preserve document-owned contextual panels across operation dialogs.
replace_file("src/Mod/Assembly/Gui/ViewProviderAssembly.h", [
    ('''#pragma once

#include <QCoreApplication>
#include <QMetaObject>
#include <fastsignals/signal.h>

#include <Mod/Assembly/AssemblyGlobal.h>

''', '''#pragma once

#include <QCoreApplication>
#include <QMetaObject>
#include <QPointer>
#include <fastsignals/signal.h>

#include <Mod/Assembly/AssemblyGlobal.h>

'''),
    ('''        IsolateMode mode,
        std::set<App::DocumentObject*>& visited
    );

    TaskAssemblyMessages* taskSolver {nullptr};

    QMetaObject::Connection workbenchConnection;
    fastsignals::connection connectActivatedVP;
    fastsignals::connection connectSolverUpdate;
''', '''        IsolateMode mode,
        std::set<App::DocumentObject*>& visited
    );

    QPointer<TaskAssemblyMessages> taskSolver;

    QMetaObject::Connection workbenchConnection;
    fastsignals::connection connectActivatedVP;
    fastsignals::connection connectSolverUpdate;
'''),
])

# General freehand selection uses the native transient selection handler.
# Append enum values so existing selection modes retain their numeric identity.
replace_file("src/Gui/View3DInventorViewer.h", [
    ('''        Clip = 4,       /**< Clip objects using a lasso. */
    };
''', '''        Clip = 4,       /**< Clip objects using a lasso. */
        Freehand = 5,   /**< Select objects using a dragged freehand outline. */
    };
'''),
])
replace_file("src/Gui/Navigation/NavigationStyle.cpp", [
    ('''        case Clip:
            mouseSelection = new PolyClipSelection();
            break;
        default:
''', '''        case Clip:
            mouseSelection = new PolyClipSelection();
            break;
        case Freehand: {
            auto* freehand = new FreehandSelection();
            freehand->setClosed(true);
            mouseSelection = freehand;
            break;
        }
        default:
'''),
])
freehand_command = '''//===========================================================================
// Std_FreehandSelection
//===========================================================================

DEF_STD_CMD_A(StdFreehandSelection)

StdFreehandSelection::StdFreehandSelection()
    : Command("Std_FreehandSelection")
{
    sGroup = "Standard-View";
    sMenuText = QT_TR_NOOP("&Freehand Selection");
    sToolTipText = QT_TR_NOOP("Selects objects inside a dragged freehand outline");
    sWhatsThis = "Std_FreehandSelection";
    sStatusTip = sToolTipText;
    sPixmap = "edit-select-box";
    eType = AlterSelection;
}

bool StdFreehandSelection::isActive()
{
    return canStartGeometricSelection();
}

static void doFreehandSelect(void* ud, SoEventCallback* cb)
{
    auto viewer = static_cast<Gui::View3DInventorViewer*>(cb->getUserData());
    // A short stroke must not turn into the two-point rectangular selection.
    if (viewer->getPolygon().size() >= 3) {
        doSelect(ud, cb);
    }
}

void StdFreehandSelection::activated(int iMsg)
{
    Q_UNUSED(iMsg);
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    if (view) {
        View3DInventorViewer* viewer = view->getViewer();
        if (canStartGeometricSelection()) {
            int mode = viewer->navigationStyle()->getViewingMode();
            if (mode != Gui::NavigationStyle::IDLE) {
                SoKeyboardEvent ev;
                viewer->navigationStyle()->processEvent(&ev);
            }

            QCursor cursor = SelectionCallbackHandler::makeCursor(
                viewer,
                QSize(32, 32),
                "edit-select-box-cross",
                6,
                6
            );
            SelectionCallbackHandler::Create(
                viewer,
                View3DInventorViewer::Freehand,
                cursor,
                doFreehandSelect,
                nullptr
            );
        }
    }
}

'''
replace_file("src/Gui/CommandView.cpp", [
    ('''public:
    // Creates a selection handler used to implement the common behaviour of BoxZoom, BoxSelection
''', '''public:
    ~SelectionCallbackHandler()
    {
        QObject::disconnect(ownerDestroyed);
    }

    static bool isRunning()
    {
        return static_cast<bool>(currentSelectionHandler);
    }

    // Creates a selection handler used to implement the common behaviour of BoxZoom, BoxSelection
'''),
    ('''    void* userData;
    bool prevSelectionEn;
''', '''    void* userData;
    bool prevSelectionEn;
    bool freehandSelection {false};
    QObject* ownerView {nullptr};
    QMetaObject::Connection ownerDestroyed;
'''),
    ('''            currentSelectionHandler->fnCb = doFunction;
            currentSelectionHandler->prevSelectionCursor = viewer->cursor();
''', '''            currentSelectionHandler->fnCb = doFunction;
            currentSelectionHandler->ownerView = viewer;
            currentSelectionHandler->ownerDestroyed = QObject::connect(
                viewer,
                &QObject::destroyed,
                qApp,
                [](QObject* owner) {
                    if (currentSelectionHandler && currentSelectionHandler->ownerView == owner) {
                        // The render callbacks die with the viewer. Release the
                        // shared handler without querying a disposing document.
                        currentSelectionHandler.reset();
                    }
                }
            );
            currentSelectionHandler->freehandSelection
                = selectionMode == View3DInventorViewer::Freehand;
            currentSelectionHandler->prevSelectionCursor = viewer->cursor();
'''),
    ('''            if (mbe->getButton() == SoMouseButtonEvent::BUTTON1
                && mbe->getState() == SoButtonEvent::UP) {
                if (selectionHandler && selectionHandler->fnCb) {
''', '''            // A freehand outline can also Finish/Cancel from its right-click
            // menu. Its mouse model has already stopped before this callback.
            const bool freehandMenuClosed = selectionHandler && selectionHandler->freehandSelection
                && mbe->getButton() == SoMouseButtonEvent::BUTTON2 && !view->isSelecting();
            if (mbe->getState() == SoButtonEvent::UP
                && (mbe->getButton() == SoMouseButtonEvent::BUTTON1 || freehandMenuClosed)) {
                if (selectionHandler && selectionHandler->fnCb) {
'''),
    ('            // No other mouse events available from Coin3D to implement right mouse up abort',
     '            // Other mouse releases keep the current selection model unchanged.'),
    ('''        Application::Instance->commandManager().testActive();
        currentSelectionHandler = nullptr;
''', '''        currentSelectionHandler = nullptr;
        Application::Instance->commandManager().testActive();
'''),
    ('DEF_3DV_CMD(StdBoxSelection)', 'DEF_STD_CMD_A(StdBoxSelection)'),
    ('DEF_3DV_CMD(StdBoxElementSelection)', 'DEF_STD_CMD_A(StdBoxElementSelection)'),
    ('''void StdBoxSelection::activated(int iMsg)
''', '''static bool canStartGeometricSelection()
{
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    auto viewer = view ? view->getViewer() : nullptr;
    return viewer && !SelectionCallbackHandler::isRunning() && !viewer->isSelecting()
        && viewer->isSelectionEnabled();
}

bool StdBoxSelection::isActive()
{
    return canStartGeometricSelection();
}

void StdBoxSelection::activated(int iMsg)
'''),
    ('''void StdBoxElementSelection::activated(int iMsg)
''', '''bool StdBoxElementSelection::isActive()
{
    return canStartGeometricSelection();
}

void StdBoxElementSelection::activated(int iMsg)
'''),
    ('''void StdBoxSelection::activated(int iMsg)
{
    Q_UNUSED(iMsg);
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    if (view) {
        View3DInventorViewer* viewer = view->getViewer();
        if (!viewer->isSelecting()) {
''', '''void StdBoxSelection::activated(int iMsg)
{
    Q_UNUSED(iMsg);
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    if (view) {
        View3DInventorViewer* viewer = view->getViewer();
        if (canStartGeometricSelection()) {
'''),
    ('''void StdBoxElementSelection::activated(int iMsg)
{
    Q_UNUSED(iMsg);
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    if (view) {
        View3DInventorViewer* viewer = view->getViewer();
        if (!viewer->isSelecting()) {
''', '''void StdBoxElementSelection::activated(int iMsg)
{
    Q_UNUSED(iMsg);
    auto view = qobject_cast<View3DInventor*>(getMainWindow()->activeWindow());
    if (view) {
        View3DInventorViewer* viewer = view->getViewer();
        if (canStartGeometricSelection()) {
'''),
    ('''//===========================================================================
// Std_BoxElementSelection
//===========================================================================
''', freehand_command + '''//===========================================================================
// Std_BoxElementSelection
//===========================================================================
'''),
    ('''    rcCmdMgr.addCommand(new StdBoxSelection());
    rcCmdMgr.addCommand(new StdBoxElementSelection());
''', '''    rcCmdMgr.addCommand(new StdBoxSelection());
    rcCmdMgr.addCommand(new StdFreehandSelection());
    rcCmdMgr.addCommand(new StdBoxElementSelection());
'''),
])

# The diagonal bounding-box shortcut is valid only for two-point rectangles.
# Arbitrary outlines must use the existing center/polygon test instead.
replace_file("src/Gui/Selection/BoxSelection.cpp", [
    (''' * @param[in] mat Accumulated transformation matrix.
 * @param[in] transform Whether to apply object transforms while resolving geometry.
''', ''' * @param[in] mat Accumulated transformation matrix.
 * @param[in] rectangularSelection Whether the source polygon is a two-point rectangle.
 * @param[in] transform Whether to apply object transforms while resolving geometry.
'''),
    ('''    const Base::Polygon2d& polygon,
    const Base::Matrix4D& mat,
    bool transform = true,
''', '''    const Base::Polygon2d& polygon,
    const Base::Matrix4D& mat,
    bool rectangularSelection,
    bool transform = true,
'''),
    ('''        if (polygon.Contains(Base::Vector2d(bbox.MinX, bbox.MinY))
            && polygon.Contains(Base::Vector2d(bbox.MaxX, bbox.MaxY))) {
''', '''        if (rectangularSelection && polygon.Contains(Base::Vector2d(bbox.MinX, bbox.MinY))
            && polygon.Contains(Base::Vector2d(bbox.MaxX, bbox.MaxY))) {
'''),
    ('''        const auto& sels
            = getBoxSelection(svp, mode, selectElement, proj, polygon, smat, false, depth + 1);
''', '''        const auto& sels = getBoxSelection(
            svp, mode, selectElement, proj, polygon, smat, rectangularSelection, false, depth + 1
        );
'''),
    ('''        for (auto& sub : getBoxSelection(vp, selectionMode, selectElement, proj, polygon, mat)) {
''', '''        for (auto& sub : getBoxSelection(
                 vp, selectionMode, selectElement, proj, polygon, mat, glPolygon.size() == 2
             )) {
'''),
])

patch = []
for filename, (before, after) in changes.items():
    patch.append("diff --git a/%s b/%s\n" % (filename, filename))
    if not before:
        patch.append("new file mode 100644\n")
    patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                    fromfile="a/" + filename if before else "/dev/null",
                                    tofile="b/" + filename))
(root / "patches/0001-fission-identity-navigation.patch").write_text("".join(patch), encoding="utf-8", newline="\n")
print("Prepared %d source adaptations; upstream working tree unchanged." % len(changes))
