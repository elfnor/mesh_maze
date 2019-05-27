# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

"""
Generate a maze on a selection of the mesh
Uses the recursive backtracker maze algorithm
"""

import bpy
import bmesh


from .mesh_maze import generate_maze

bl_info = {
    "name": "Maze any Mesh",
    "author": "elfnor <elfnor.com>",
    "version": (1, 2),
    "blender": (2, 80, 0),
    "location": "View3D EditMesh Menu -> Maze mesh selection",
    "description": "Convert any mesh to a maze pattern",
    "warning": "",
    "category": "Mesh",
}


class MESH_OT_maze_mesh(bpy.types.Operator):
    """Generate maze on mesh"""
    bl_idname = "mesh.maze_mesh"
    bl_label = "Maze mesh selection"
    bl_description = "Generate a maze on selected part of mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ check in edit mode"""
        obj = context.edit_object
        return obj is not None and obj.type == 'MESH'

    link_centers = []
    vert_centers = []

    # properties for bevel operator
    offset_modes = (
        ("OFFSET", "Offset", "Width is offset of new edges from original", 1),
        ("WIDTH", "Width", "Width is width of new face", 2),
        ("DEPTH", "Depth", "Width is distance from original edge to bevel face", 3),
        ("PERCENT", "Percent", "Width is percent of adjacent edge length", 4)
    )

    wall_types = (
        ("0", "Thick", "Boundary wall extends to edge of selection", 0),
        ("1", "Thin", "Boundary wall is similar thickness to internal walls", 1),
        ("2", "None", "Boundary wall is not extruded")
    )

    offset_type = bpy.props.EnumProperty(
        name='Bevel Amount Type',
        description="What distance Width measures",
        items=offset_modes)

    offset = bpy.props.FloatProperty(
        name='Width',
        description='path width',
        default=0.1, soft_min=0,
        soft_max=1.0, precision=3)

    use_clamp_overlap = bpy.props.BoolProperty(
        name='Clamp Overlap',
        description='Do not allow bevel edges to overlap',
        default=False)

    use_loop_slide = bpy.props.BoolProperty(
        name='Loop Slide',
        description='Prefer slide along edge to even widths',
        default=True)

    # properties for inset operator

    use_even_offset = bpy.props.BoolProperty(
        name='Offset Even',
        description='Scale the offset to give more even thickness',
        default=False)

    use_relative_offset = bpy.props.BoolProperty(
        name='Offset Relative',
        description='Scale the offset by surrounding geometry',
        default=False)

    thickness = bpy.props.FloatProperty(
        name='Thickness',
        description='wall width at top',
        default=0.0, soft_min=-1.0, soft_max=1.0, precision=4)

    depth = bpy.props.FloatProperty(
        name='Extrude',
        description='wall height',
        default=0.1, soft_min=-1.0, soft_max=1.0, precision=4)

    use_outset = bpy.props.BoolProperty(
        name='Outset',
        description='Outset rather than inset',
        default=False)

    # properties for maze
    def update_maze(self, context):
        """
        maze path needs updating after changing rseed or braid
        """
        self.update = True

    rseed = bpy.props.IntProperty(
        name='Random seed',
        description='redo maze pattern',
        default=0, min=0, max=100,
        update=update_maze)

    braid = bpy.props.FloatProperty(
        name='Braiding',
        description='fraction of dead ends to make into loops',
        default=0, min=0.0, max=1.0, precision=2,
        update=update_maze)

    boundary_type = bpy.props.EnumProperty(
        name='Boundary Wall Type',
        description="type of wall on boundary of maze",
        items=wall_types, default="1")

    options = bpy.props.BoolProperty(
        name='Advanced Options',
        description='More options',
        default=False)

    update = bpy.props.BoolProperty(
        name='update maze',
        description='update maze',
        default=True)

    def draw(self, context):
        """draw tool operator panel"""
        layout = self.layout

        col = layout.column()

        # row = col.row()
        col.label(text='Maze Parameters')
        col.prop(self, 'rseed')
        col.prop(self, 'braid')
        col.prop(self, 'boundary_type')
        col.prop(self, 'options')

        col.label(text='Path Paramters')
        col.prop(self, 'offset_type', text='')
        col.prop(self, 'offset')
        if self.options:
            col.prop(self, 'use_clamp_overlap')
            col.prop(self, 'use_loop_slide')

        col.label(text='Wall Paramters')
        col.prop(self, 'use_relative_offset')
        col.prop(self, 'depth')
        if self.options:
            col.prop(self, 'use_even_offset')
            col.prop(self, 'thickness')
            col.prop(self, 'use_outset')

    def get_maze_params(self):
        """
        build maze parameters dictionary from properties
        """
        maze_params = {}
        maze_params['maze_update'] = self.update
        maze_params['rseed'] = self.rseed
        maze_params['link_centers'] = self.link_centers
        maze_params['vert_centers'] = self.vert_centers
        maze_params['offset'] = self.offset
        maze_params['offset_type'] = self.offset_type
        maze_params['use_loop_slide'] = self.use_loop_slide
        maze_params['use_clamp_overlap'] = self.use_clamp_overlap
        maze_params['boundary_type'] = int(self.boundary_type)
        maze_params['depth'] = self.depth
        maze_params['thickness'] = self.thickness
        maze_params['use_even_offset'] = self.use_even_offset
        maze_params['use_outset'] = self.use_outset
        maze_params['use_relative_offset'] = self.use_relative_offset
        maze_params['braid'] = self.braid

        return maze_params

    def execute(self, context):
        """build maze
        """
        obj = context.object

        bm = bmesh.from_edit_mesh(obj.data)

        if len(self.vert_centers) == 0:
            self.update = True
        maze_params = self.get_maze_params()
        bpy.ops.mesh.select_mode(type='EDGE')

        bm, self.link_centers, self.vert_centers = generate_maze(bm, maze_params)
        self.update = False

        bmesh.update_edit_mesh(obj.data, destructive=True)

        return {'FINISHED'}


def menu_func(self, context):
    """ single menu entry"""
    self.layout.operator("mesh.maze_mesh")


def register():
    """ add to specials menu"""
    bpy.utils.register_class(MESH_OT_maze_mesh)
    bpy.types.VIEW3D_MT_edit_mesh.prepend(menu_func)


def unregister():
    """ remove from specials menu"""
    bpy.utils.unregister_class(MESH_OT_maze_mesh)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)
    print('unregistered')


if __name__ == "__main__":
    register()
