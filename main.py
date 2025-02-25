from itertools import chain
import json
import os

import bpy
from mathutils import Vector
from bl_ui.generic_ui_list import draw_ui_list

from .subdivide import subdivideCurve
from .fractals import Generator, parse_gene, get_initiator_matrices


class CurveDefItem(bpy.types.PropertyGroup):
    complex_integer: bpy.props.IntVectorProperty(name="Complex Integer", size=2, default=(0, 0), description="Complex integer coordinates used define how the curve is generated.")
    transform_flags: bpy.props.BoolVectorProperty(name="Transform Flags", size=2, default=(False, False), description="Reverse flag, Mirror flag")


class CurveDefItemList(bpy.types.UIList):
    bl_idname = "FRACTALS_UL_CurveDefItemList"
    use_filter_show = False
    use_filter_sort_alpha = False
    use_filter_sort_lock = True

    def draw_item(self, context, layout, data, item: CurveDefItem, icon, active_data, active_property, index, flt_flag=0):
        integer = item.complex_integer
        reverse_flag, mirror_flag = item.transform_flags
        col = layout.column()
        row = col.row(align=True)
        total = len(data.fractal_curvedef_items)
        row.label(text=f"{index + 1:2d}/{total:2d}: ({integer[0]}, {integer[1]})")
        icon = 'UV_SYNC_SELECT' if reverse_flag else 'PROP_OFF'
        row.prop(item, "transform_flags", index=0, text="", icon=icon, emboss=False)
        icon = 'MOD_MIRROR' if mirror_flag else 'PROP_OFF'
        row.prop(item, "transform_flags", index=1, text="", icon=icon, emboss=False)


def on_gene_changed(self, context):
    generator = Generator(parse_gene(self.gene), name=self.name, gene=self.gene)
    self.family = str(generator.integer)
    scene = context.scene
    scene.fractal_domain = generator.domain.name
    on_preset_item_selected(self, context)


class CurvePresetItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    gene: bpy.props.StringProperty(name="Gene", update=on_gene_changed)
    family: bpy.props.StringProperty(name="Family")


class CurvePresetItemList(bpy.types.UIList):
    bl_idname = "FRACTALS_UL_CurvePresetItemList"

    def draw_item(self, context, layout, data, item: CurvePresetItem, icon, active_data, active_property, index, flt_flag):
        col = layout.column()
        row = col.row(align=True)
        row.alignment = 'RIGHT'
        row.label(text=f'{item.family:10s}')
        row.prop(item, "name", text="", emboss=False)


class FractalFamilyPanel(bpy.types.Panel):
    bl_label = "Fractal Family"
    bl_idname = "FRACTALS_PT_fractalfamily"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fractals"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        draw_ui_list(
            layout, context,
            class_name='FRACTALS_UL_CurvePresetItemList',
            list_path="scene.fractal_preset_items",
            active_index_path="scene.fractal_preset_active_index",
            unique_id="FRACTALS_CURVE_PRESET_LIST",
        )

        preset_items = scene.fractal_preset_items
        active_index = scene.fractal_preset_active_index
        if preset_items:
            # Edit current selected preset
            item = preset_items[active_index]
            row = layout.row(align=True)
            row.prop(item, "name", text="")
            # row.label(text="", icon='BLANK1')
            row.operator('fractalfamily.save_preset', text='', icon='FILE_TICK')
            row = layout.row()
            row.prop(item, "gene", text="")

        row1 = layout.row()
        row1.alignment = 'RIGHT'
        # row1.label(text='', icon='BLANK1')
        row1.label(text='Domain: ')
        col = row1.column()
        row = col.row(align=True)
        row.prop_enum(scene, 'fractal_domain', 'G')
        row.prop_enum(scene, 'fractal_domain', 'E')
        col = row1.column()
        row = col.row()
        row.operator('fractalfamily.load_preset', text='', icon='ASSET_MANAGER')

        draw_ui_list(
            layout, context,
            class_name='FRACTALS_UL_CurveDefItemList',
            list_path="scene.fractal_curvedef_items",
            active_index_path="scene.fractal_curvedef_active_index",
            unique_id="fractal_generator_id",
        )

        generator_items = scene.fractal_curvedef_items
        active_index = scene.fractal_curvedef_active_index

        if generator_items:
            item = generator_items[active_index]
            row = layout.row()
            box = row.box()
            row1 = box.row(align=True)
            row1.prop(item, "complex_integer", index=0, text="")
            row1.prop(item, "complex_integer", index=1, text="")
            row1.label(text="", icon='BLANK1')
            icon = 'UV_SYNC_SELECT' if item.transform_flags[0] else 'PROP_OFF'
            row1.prop(item, "transform_flags", index=0, text="", icon=icon, emboss=False)
            icon = 'MOD_MIRROR' if item.transform_flags[1] else 'PROP_OFF'
            row1.prop(item, "transform_flags", index=1, text="", icon=icon, emboss=False)
            row.label(text="", icon='BLANK1')
            row = layout.row()
            row.prop(scene, 'fractal_level', text='')
            split = row.split(factor=0.5, align=True)
            split.prop_enum(scene, 'fractal_spline_type', 'POLY')
            split.prop_enum(scene, 'fractal_spline_type', 'SMOOTH')
            row = layout.row()
            row.prop(scene.fractal_initiator_spline, 'curve', text='', placeholder="Initiator Spline")
            row.prop(scene.fractal_initiator_spline, 'reverse', text='', icon='ARROW_LEFTRIGHT')
            row = layout.row()
            row.operator('fractalfamily.create_teragon_curves', text='Create Teragon Curves', icon='CURVE_BEZCURVE')


class FRACTALFAMILY_OT_load_preset(bpy.types.Operator):
    bl_idname = "fractalfamily.load_preset"
    bl_label = "Load Preset"
    bl_description = "Load presets of fractal curves definitons from file."

    def execute(self, context):
        scene = context.scene
        items = scene.fractal_preset_items
        items.clear()
        file_path = os.path.join(os.path.dirname(__file__), 'presets.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            preset_curves = json.load(f)
        for info in preset_curves:
            item = items.add()
            for key, value in info.items():
                setattr(item, key, value)
        on_preset_item_selected(self, context)
        return {'FINISHED'}


class FRACTALFAMILY_OT_save_preset(bpy.types.Operator):
    bl_idname = "fractalfamily.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save preset list to file, same name will be ignored."

    def execute(self, context):
        scene = context.scene
        items = scene.fractal_preset_items
        file_path = os.path.join(os.path.dirname(__file__), 'presets.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            preset_curves = json.load(f)
        modified = False
        for item in items:
            if any(item.name == info['name'] for info in preset_curves):
                continue
            modified = True
            info = {'name': item.name, 'gene': item.gene, 'family': item.family}
            preset_curves.append(info)
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(preset_curves, f, indent=4)
        return {'FINISHED'}


def create_curve_poly(points, name='Curve', noSegs=1, is_closed=False):
    pts: list[Vector] = []
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        for j in range(noSegs):
            t = j / noSegs
            pts.append(p1 + (p2 - p1) * t)
    pts.append(points[-1])
    curve = bpy.data.curves.new(name=name, type="CURVE")
    spline = curve.splines.new("BEZIER")
    bpts = spline.bezier_points
    bpts.add(len(pts) - 1)
    points_unpacked = list(chain.from_iterable(co.to_tuple() for co in pts))
    bpts.foreach_set("co", points_unpacked)
    for i in range(len(bpts)):
        bpts[i].handle_left_type = 'VECTOR'
        bpts[i].handle_right_type = 'VECTOR'
    spline.use_cyclic_u = is_closed
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj


def create_curve_smooth(points, name='Curve', noSegs=1, is_closed=False):
    curve = bpy.data.curves.new(name=name, type="CURVE")
    spline = curve.splines.new("BEZIER")
    spline.use_cyclic_u = is_closed
    bpts = spline.bezier_points
    bpts.add(len(points) - 1)
    for i, point in enumerate(points):
        bpts[i].co = point
        bpts[i].handle_left_type = 'AUTO'
        bpts[i].handle_right_type = 'AUTO'
    subdivideCurve(curve, noSegs)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj


class FRACTALFAMILY_OT_create_teragon_curves(bpy.types.Operator):
    bl_idname = "fractalfamily.create_teragon_curves"
    bl_label = "Create Teragon Curves"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        generator_items = scene.fractal_curvedef_items
        chars = [scene.fractal_domain, ]
        for item in generator_items:
            a, b = item.complex_integer
            r = 1 if item.transform_flags[0] else 0
            m = 1 if item.transform_flags[1] else 0
            chars.extend([str(a), str(b), str(r), str(m)])
        gene = ' '.join(chars)
        generator = Generator(parse_gene(gene), gene=gene)
        subdivision = len(generator.elements)
        is_closed = False
        level = scene.fractal_level
        generator.update_level_points(level)
        spline_type = scene.fractal_spline_type
        initiator_spline: bpy.types.Curve = scene.fractal_initiator_spline.curve
        initiator_points = [Vector(), generator.integer.coord]
        if initiator_spline:
            spline = initiator_spline.splines.active
            if spline.use_cyclic_u:
                is_closed = True
            if spline.type == 'BEZIER' and len(spline.bezier_points) > 1:
                initiator_points = [p.co for p in spline.bezier_points]
            elif len(spline.points) > 1:
                initiator_points = [p.co.to_3d() for p in spline.points]
            if scene.fractal_initiator_spline.reverse:
                initiator_points.reverse()
        initiator_matrices = get_initiator_matrices(initiator_points, generator, is_closed)
        for i, points in enumerate(generator.level_points):
            teragon_points = [initiator_points[0]]
            for matrix in initiator_matrices:
                teragon_points.extend(matrix @ point for point in points)
            if is_closed:
                teragon_points.pop()
            # subdivide count is proportional to the level difference
            if spline_type == 'POLY':
                obj = create_curve_poly(teragon_points, f"Teragon {i}", subdivision ** (level - i), is_closed)
            else:
                obj = create_curve_smooth(teragon_points, f"Teragon {i}", subdivision ** (level - i), is_closed)
            obj.select_set(True)
            if i == 0:
                obj.name = "Teragon"
                obj.data.name = "Teragon"
                context.view_layer.objects.active = obj
        return {'FINISHED'}


def on_preset_item_selected(self, context):
    scene = context.scene
    active_index = scene.fractal_preset_active_index
    preset_items = scene.fractal_preset_items
    preset_item: CurvePresetItem = preset_items[active_index]
    if not preset_item.gene:
        return
    scene.fractal_domain = preset_item.family[0]
    scene.fractal_curvedef_active_index = 0
    generator_items = scene.fractal_curvedef_items
    generator_items.clear()
    generator = Generator(parse_gene(preset_item.gene), preset_item.name, preset_item.gene)
    for element in generator.elements:
        integer, transform = element.integer, element.transform
        item = generator_items.add()
        item.complex_integer = (integer.a, integer.b)
        item.transform_flags = (bool(transform[0]), bool(transform[1]))


class InitiatorSplineProp(bpy.types.PropertyGroup):
    curve: bpy.props.PointerProperty(type=bpy.types.Curve, name="Initiator Spline", description="Keep empty to use the segment from origin to the last accumulated cooridnate.")
    reverse: bpy.props.BoolProperty(name="Reverse", default=False, description="Use the reversed sequence of the initiator spline points.")


def register():
    bpy.types.Scene.fractal_curvedef_items = bpy.props.CollectionProperty(type=CurveDefItem)
    bpy.types.Scene.fractal_curvedef_active_index = bpy.props.IntProperty(default=0, name="Element to define the fractal curve")
    bpy.types.Scene.fractal_preset_items = bpy.props.CollectionProperty(type=CurvePresetItem)
    bpy.types.Scene.fractal_preset_active_index = bpy.props.IntProperty(default=0, update=on_preset_item_selected)
    bpy.types.Scene.fractal_domain = bpy.props.EnumProperty(items=[("G", "Gaussian", ""), ("E", "Eisenstein", "")])
    bpy.types.Scene.fractal_spline_type = bpy.props.EnumProperty(items=[("POLY", "Poly", ""), ("SMOOTH", "Smooth", "")], description="Spline type of the generated fractal curves")
    bpy.types.Scene.fractal_level = bpy.props.IntProperty(default=4, min=1, max=20, name="Level of fractal curves")
    bpy.types.Scene.fractal_initiator_spline = bpy.props.PointerProperty(type=InitiatorSplineProp)


def unregister():
    del bpy.types.Scene.fractal_curvedef_items
    del bpy.types.Scene.fractal_curvedef_active_index
    del bpy.types.Scene.fractal_preset_items
    del bpy.types.Scene.fractal_preset_active_index
    del bpy.types.Scene.fractal_domain
    del bpy.types.Scene.fractal_spline_type
    del bpy.types.Scene.fractal_level
    del bpy.types.Scene.fractal_initiator_spline
