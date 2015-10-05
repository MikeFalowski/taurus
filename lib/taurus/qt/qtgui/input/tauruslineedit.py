#!/usr/bin/env python

#############################################################################
##
## This file is part of Taurus
## 
## http://taurus-scada.org
##
## Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
## 
## Taurus is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Taurus is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public License
## along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
##
#############################################################################

"""This module provides a set of basic taurus widgets based on QLineEdit"""

__all__ = ["TaurusValueLineEdit", "TaurusConfigLineEdit"]

__docformat__ = 'restructuredtext'

import sys, taurus.core
from taurus.external.qt import Qt
from taurus.external.pint import Quantity, DimensionalityError
from taurus.qt.qtgui.base import TaurusBaseWritableWidget
from taurus.core import DataType


_String = str
try:
    _String = Qt.QString
except AttributeError:
    _String = str

class _PintValidator(Qt.QValidator):
    """A QValidator for pint Quantities"""
    _top = None
    _bottom = None

    @property
    def top(self):
        """
        :return: (Quantity or None) maximum acceptable or None if it should not
                 be enforced
        """
        return self._top

    def setTop(self, top):
        """
        Set maximum limit
        :param q: (Quantity or None) maximum acceptable value value
        """
        self._top = Quantity(top)

    @property
    def bottom(self):
        """
        :return: (Quantity or None) minimum acceptable or None if it should not
                 be enforced
        """
        return self._bottom

    def setBottom(self, bottom):
        """
        Set minimum limit
        :param q: (Quantity or None) minimum acceptable value value
        """
        self._bottom = Quantity(bottom)

    def _validate(self, input, pos):
        """Reimplemented from :class:`QValidator` to validate if the input
        string is a representation of a quantity within the set bottom and top
        limits
        """
        try:
            q = Quantity(input)
        except:
            return Qt.QValidator.Intermediate, input, pos
        try:
            if self.bottom is not None and q < self.bottom:
                return Qt.QValidator.Invalid, input, pos
            if self.top is not None and q > self.top:
                return Qt.QValidator.Invalid, input, pos
        except DimensionalityError:
            return Qt.QValidator.Invalid, input, pos
        return Qt.QValidator.Acceptable, input, pos

    def _validate_oldQt(self, input, pos):
        """Old Qt (v4.4.) -compatible implementation of validate"""
        state, _, pos =  self._validate(input, pos)
        return state,pos

    # select the appropriate implementation of validate. See:
    # https://www.mail-archive.com/pyqt@riverbankcomputing.com/msg26344.html
    validate = Qt.PYQT_QSTRING_API_1 and _validate_oldQt or _validate



class TaurusValueLineEdit(Qt.QLineEdit, TaurusBaseWritableWidget):

    __pyqtSignals__ = ("modelChanged(const QString &)",)

    def __init__(self, qt_parent = None, designMode = False):
        name = self.__class__.__name__
        self.call__init__wo_kw(Qt.QLineEdit, qt_parent)
        self.call__init__(TaurusBaseWritableWidget, name, designMode=designMode)
        self._enableWheelEvent = False
        self.__minAlarm = -float("inf")
        self.__maxAlarm = float("inf")
        self.__minLimit = -float("inf")
        self.__maxLimit = float("inf")

        self.setAlignment(Qt.Qt.AlignRight)
        self.setValidator(None)

        self.connect(self, Qt.SIGNAL('textChanged(const QString &)'), self.valueChanged)
        self.connect(self, Qt.SIGNAL('returnPressed()'), self.writeValue)
        self.connect(self, Qt.SIGNAL('valueChanged'), self.updatePendingOperations)
        self.connect(self, Qt.SIGNAL('editingFinished()'), self._onEditingFinished)

    def _updateValidator(self, value):
        '''This method sets a validator depending on the data type'''
        if value.type in (DataType.Integer,DataType.Float):
            validator= _PintValidator(self)
            validator.setBottom(self.__minLimit)
            validator.setTop(self.__maxLimit)
            self.setValidator(validator)
            self.debug("_PintValidator set with limits=[%f,%f]",
                       self.__minLimit, self.__maxLimit)
        else: #@TODO Other validators can be configured for other types (e.g. with string lengths, tango names,...)
            self.setValidator(None)
            self.debug("Validator disabled")

    def __decimalDigits(self, fmt):
        '''returns the number of decimal digits from a format string
        (or None if they are not defined)''' 
        try:
            if fmt[-1].lower() in ['f','g'] and '.' in fmt:
                return int(fmt[:-1].split('.')[-1])
            else:
                return None
        except:
            return None

    def _onEditingFinished(self):
        '''slot for performing autoapply only when edition is finished'''
        if self._autoApply:
            self.writeValue()

    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    # TaurusBaseWritableWidget overwriting
    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    def valueChanged(self, *args):
        '''reimplement to avoid autoapply on every partial edition'''
        self.emitValueChanged()

    def handleEvent(self, evt_src, evt_type, evt_value):
        if evt_type == taurus.core.taurusbasetypes.TaurusEventType.Config:
            attr = self.getModelObj()
            self.__minAlarm, self.__maxAlarm = attr.alarm
            self.__minLimit, self.__maxLimit = attr.range

            self._updateValidator(evt_value)
        TaurusBaseWritableWidget.handleEvent(self, evt_src, evt_type, evt_value)

    def _inAlarm(self, v):
        try: return not(self.__minAlarm < float(v) < self.__maxAlarm)
        except: return False #this will return false for non-numerical values

    def _outOfRange(self, v):
        validator = self.validator()
        if validator:
            return validator.validate(_String(str(v)), 0)[0] != validator.Acceptable
        else: #fallback, only for numeric typess (returns False for other types)
            try: return not(self.__minLimit <= float(v) <=  self.__maxLimit)
            except: return False

    def updateStyle(self):
        TaurusBaseWritableWidget.updateStyle(self)
        color, weight = 'black', 'normal' #default case: the value is in normal range with no pending changes
        v = self.getValue()
        if self._outOfRange(v): #the value is invalid and can't be applied
            color = 'gray'
        elif self._inAlarm(v): #the value is valid but in alarm range...
            color = 'orange'
            if self.hasPendingOperations(): #...and some change is pending
                weight = 'bold'
        elif self.hasPendingOperations(): #the value is in valid range with pending changes
            color, weight= 'blue','bold'
        self.setStyleSheet('TaurusValueLineEdit {color: %s; font-weight: %s}'%(color,weight))

    def wheelEvent(self, evt):
        if not self.getEnableWheelEvent() or Qt.QLineEdit.isReadOnly(self):
            return Qt.QLineEdit.wheelEvent(self, evt)
        model = self.getModelObj()
        if model is None or not model.isNumeric():
            return Qt.QLineEdit.wheelEvent(self, evt)

        evt.accept()
        numDegrees = evt.delta() / 8
        numSteps = numDegrees / 15
        modifiers = evt.modifiers()
        if modifiers & Qt.Qt.ControlModifier:
            numSteps *= 10
        elif (modifiers & Qt.Qt.AltModifier) and model.isFloat():
            numSteps *= .1
        self._stepBy(numSteps)

    def keyPressEvent(self, evt):
        if evt.key() in (Qt.Qt.Key_Return, Qt.Qt.Key_Enter):
            Qt.QLineEdit.keyPressEvent(self, evt)
            evt.accept()
            return
        if Qt.QLineEdit.isReadOnly(self):
            return Qt.QLineEdit.keyPressEvent(self, evt)
        model = self.getModelObj()
        if model is None or not model.isNumeric():
            return Qt.QLineEdit.keyPressEvent(self, evt)

        if evt.key() == Qt.Qt.Key_Up:     numSteps = 1
        elif evt.key() == Qt.Qt.Key_Down: numSteps = -1
        else: return Qt.QLineEdit.keyPressEvent(self, evt)

        evt.accept()
        modifiers = evt.modifiers()
        if modifiers & Qt.Qt.ControlModifier:
            numSteps *= 10
        elif (modifiers & Qt.Qt.AltModifier) and model.isFloat():
            numSteps *= .1
        self._stepBy(numSteps)

    def _stepBy(self, v):
        self.setValue(self.getValue() + v)

    def setValue(self, v):
        model = self.getModelObj()
        if model is None:
            v_str = str(v)
        else:
            v_str = str(model.displayValue(v))
        v_str = v_str.strip()
        self.setText(v_str)

    def getValue(self):
        v_qstr = self.text()
        model = self.getModelObj()
        try:
            return model.encode(v_qstr) # TODO: Maybe this encode should disapear?
        except:
            return None

    def setEnableWheelEvent(self, b):
        self._enableWheelEvent = b

    def getEnableWheelEvent(self):
        return self._enableWheelEvent

    def resetEnableWheelEvent(self):
        self.setEnableWheelEvent(False)

    @classmethod
    def getQtDesignerPluginInfo(cls):
        ret = TaurusBaseWritableWidget.getQtDesignerPluginInfo()
        ret['module'] = 'taurus.qt.qtgui.input'
        ret['icon'] = ":/designer/lineedit.png"
        return ret

    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    # QT properties
    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    model = Qt.pyqtProperty("QString", TaurusBaseWritableWidget.getModel,
                            TaurusBaseWritableWidget.setModel,
                            TaurusBaseWritableWidget.resetModel)

    useParentModel = Qt.pyqtProperty("bool", TaurusBaseWritableWidget.getUseParentModel,
                                     TaurusBaseWritableWidget.setUseParentModel,
                                     TaurusBaseWritableWidget.resetUseParentModel)

    autoApply = Qt.pyqtProperty("bool", TaurusBaseWritableWidget.getAutoApply,
                                TaurusBaseWritableWidget.setAutoApply,
                                TaurusBaseWritableWidget.resetAutoApply)

    forcedApply = Qt.pyqtProperty("bool", TaurusBaseWritableWidget.getForcedApply,
                                  TaurusBaseWritableWidget.setForcedApply,
                                  TaurusBaseWritableWidget.resetForcedApply)

    enableWheelEvent = Qt.pyqtProperty("bool", getEnableWheelEvent,
                                       setEnableWheelEvent,
                                       resetEnableWheelEvent)



class TaurusConfigLineEdit(Qt.QLineEdit, TaurusBaseWritableWidget):
    def __init__(self, qt_parent = None, designMode = False):
        name = self.__class__.__name__
        self.call__init__wo_kw(Qt.QLineEdit, qt_parent)
        self.call__init__(TaurusBaseWritableWidget, name, designMode=designMode)

        self.connect(self, Qt.SIGNAL('textChanged(const QString &)'), self.valueChanged)
        self.connect(self, Qt.SIGNAL('returnPressed()'), self.writeValue)
        self.connect(self, Qt.SIGNAL('editingFinished()'), self._onEditingFinished)

    def _onEditingFinished(self):
        if self._autoApply: self.writeValue()

    def handleEvent(self, evt_src, evt_type, evt_value):
        self.valueChanged()

    def getModelClass(self):
        return taurus.core.taurusconfiguration.TaurusConfiguration

    def setValue(self, v):
        model = self.getModelObj()
        cfg = self._configParam
        if model is None or not cfg:
            v_str = str(v)
        else:
            v_str = str(model.getParam(cfg))
        self.blockSignals(True)
        self.setText(v_str.strip())
        self.blockSignals(False)

    def getValue(self):
        v_qstr = self.text()
        model = self.getModelObj()
        try:
            return model.encode(v_qstr)
        except:
            return None

    def setModel(self, model):
        model = str(model)
        try:
            self._configParam = model[model.rfind('=')+1:].lower()
        except:
            self._configParam = ''
        TaurusBaseWritableWidget.setModel(self,model)

    def valueChanged(self):
        model = self.getModelObj()
        if self.getValue() != str(model.getParam(self._configParam)):
            self.setStyleSheet('TaurusConfigLineEdit {color: %s; font-weight: %s}'%('blue','bold'))
        else:
            self.setStyleSheet('TaurusConfigLineEdit {color: %s; font-weight: %s}'%('black','normal'))

    def writeValue(self):
        model = self.getModelObj()
        model.setParam(str(self._configParam), str(self.text()))
        self.setStyleSheet('TaurusConfigLineEdit {color: %s; font-weight: %s}'%('black','normal'))

    @classmethod
    def getQtDesignerPluginInfo(cls):
        ret = TaurusBaseWritableWidget.getQtDesignerPluginInfo()
        ret['module'] = 'taurus.qt.qtgui.input'
        ret['icon'] = ":/designer/lineedit.png"
        return ret

#-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    # QT properties
#-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    model = Qt.pyqtProperty("QString", TaurusBaseWritableWidget.getModel,
                            setModel, TaurusBaseWritableWidget.resetModel)

    autoApply = Qt.pyqtProperty("bool", TaurusBaseWritableWidget.getAutoApply,
                                TaurusBaseWritableWidget.setAutoApply,
                                TaurusBaseWritableWidget.resetAutoApply)

    forcedApply = Qt.pyqtProperty("bool", TaurusBaseWritableWidget.getForcedApply,
                                  TaurusBaseWritableWidget.setForcedApply,
                                  TaurusBaseWritableWidget.resetForcedApply)

def main():
    import sys
    from taurus.qt.qtgui.application import TaurusApplication

    app = TaurusApplication()

    form = Qt.QWidget()
    layout = Qt.QVBoxLayout()
    form.setLayout(layout)
    for m in ('sys/tg_test/1/double_scalar',
              'sys/tg_test/1/double_scalar'
              ):
        w = TaurusValueLineEdit()
        w.setModel(m)
        layout.addWidget(w)
    form.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    sys.exit(main())
