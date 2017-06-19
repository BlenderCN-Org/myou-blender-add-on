import bpy, gpu, os, base64, struct, zlib, re
from json import loads, dumps
from pprint import pprint
from random import random
from .shader_lib_extractor import *
from . import mat_binternal
from . import mat_nodes
from . import mat_code_generator

def mat_to_json(mat, scn, layers):
    if scn.render.engine != 'CYCLES':
        # Blender internal or Blender game

        # We'll disable "this layer only" lights,
        # and restore them all unconditionally
        lamps = []
        try:
            # TODO: optimize making a list of lamps per layer?
            # TODO: update scene only when necessary?
            # export materials ordered by update requirements?
            for ob in scn.objects:
                if ob.type == 'LAMP':
                    lamp = ob.data
                    if lamp.use_own_layer and \
                            not any(a and b for a,b in zip(ob.layers, layers)):
                        lamps.append([lamp, lamp.use_diffuse, lamp.use_specular])
                        lamp.use_diffuse = lamp.use_specular = False
            scn.update()
            r = mat_binternal.mat_to_json_try(mat, scn)
        finally:
            for lamp, use_diffuse, use_specular in lamps:
                lamp.use_diffuse = use_diffuse
                lamp.use_specular = use_specular
        return r
    else:
        set_shader_lib('', mat, scn)
        # Blender Cycles or PBR branch

        # NodeTreeShaderGenerator uses platform-agnostic data
        # so we convert the tree and the lamps
        tree = mat_nodes.export_nodes_of_material(mat)
        lamps = []
        for ob in scn.objects:
            if ob.type == 'LAMP' and ob.data:
                lamps.append(dict(
                    name=ob.name,
                    lamp_type=ob.data.type,
                    use_diffuse=ob.data.use_diffuse,
                    use_specular=ob.data.use_specular,
                    use_shadow=ob.data.use_shadow,
                    shadow_buffer_type=ob.data.ge_shadow_buffer_type,
                ))

        gen = mat_code_generator.NodeTreeShaderGenerator(tree, lamps)

        code = gen.get_code()
        uniforms = gen.get_uniforms()
        varyings = gen.get_varyings()
        pprint(uniforms)
        material_type = 'BLENDER_CYCLES_PBR'
        return dict(
            type='MATERIAL',
            name=mat.name,
            material_type=material_type,
            fragment=code,
            uniforms=uniforms,
            varyings=varyings
        )


def world_material_to_json(scn):
    if scn.render.engine == 'CYCLES' and scn.world.use_nodes:
        if not get_shader_lib():
            # Create a material just to get the shader library
            mat = bpy.data.materials.new('delete_me')
            set_shader_lib('', mat, scn)
            bpy.data.materials.remove(mat)

        tree = mat_nodes.export_nodes_of_material(scn.world)
        tree['is_background'] = True
        gen = mat_code_generator.NodeTreeShaderGenerator(tree, [])

        code = gen.get_code()
        uniforms = gen.get_uniforms()
        varyings = gen.get_varyings()
        pprint(uniforms)
        material_type = 'BLENDER_CYCLES_PBR'
        return dict(
            type='MATERIAL',
            name=scn.name+'_world_background',
            material_type=material_type,
            fragment=code,
            uniforms=uniforms,
            varyings=varyings,
            fixed_z=1,
        )
    return None
