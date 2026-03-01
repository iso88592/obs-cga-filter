#include <obs-module.h>

OBS_DECLARE_MODULE()
OBS_MODULE_USE_DEFAULT_LOCALE("obs-cga-filter", "en-US")

#define SETTING_PALETTE    "palette_mode"
#define SETTING_PIXEL_SIZE "pixel_size"

// CGA colour component values (from 8-bit hex: 0x00 0x55 0xAA 0xFF)
#define C0 0.000000f
#define C1 0.333333f   // 0x55
#define C2 0.666667f   // 0xAA
#define C3 1.000000f

// 4 palettes × 4 colours × 3 channels (R,G,B)
// Palette 1 Hi:  Black / Light Cyan #55FFFF / Light Magenta #FF55FF / White #FFFFFF
// Palette 1 Lo:  Black / Cyan #00AAAA       / Magenta #AA00AA       / Light Gray #AAAAAA
// Palette 0 Hi:  Black / Light Green #55FF55/ Light Red #FF5555     / Yellow #FFFF55
// Palette 0 Lo:  Black / Green #00AA00      / Red #AA0000           / Brown #AA5500
static const float palette_data[4][4][3] = {
	{ {C0,C0,C0}, {C1,C3,C3}, {C3,C1,C3}, {C3,C3,C3} }, // Pal 1 Hi
	{ {C0,C0,C0}, {C0,C2,C2}, {C2,C0,C2}, {C2,C2,C2} }, // Pal 1 Lo
	{ {C0,C0,C0}, {C1,C3,C1}, {C3,C1,C1}, {C3,C3,C1} }, // Pal 0 Hi
	{ {C0,C0,C0}, {C0,C2,C0}, {C2,C0,C0}, {C2,C1,C0} }, // Pal 0 Lo
};

struct cga_filter_data {
	obs_source_t *context;
	gs_effect_t  *effect;
	gs_eparam_t  *param_resolution;
	gs_eparam_t  *param_pixel_size;
	gs_eparam_t  *param_pal[4];
	int           palette_mode;
	int           pixel_size;
};

static const char *cga_get_name(void *unused)
{
	UNUSED_PARAMETER(unused);
	return "CGA Dither";
}

static obs_properties_t *cga_get_properties(void *unused)
{
	UNUSED_PARAMETER(unused);

	obs_properties_t *props = obs_properties_create();
	obs_property_t   *p     = obs_properties_add_list(
		props, SETTING_PALETTE, "Palette",
		OBS_COMBO_TYPE_LIST, OBS_COMBO_FORMAT_INT);

	obs_property_list_add_int(p, "Palette 1, Hi \xe2\x80\x94 Cyan / Magenta / White",     0);
	obs_property_list_add_int(p, "Palette 1, Lo \xe2\x80\x94 Cyan / Magenta / Gray",      1);
	obs_property_list_add_int(p, "Palette 0, Hi \xe2\x80\x94 Green / Red / Yellow",       2);
	obs_property_list_add_int(p, "Palette 0, Lo \xe2\x80\x94 Green / Red / Brown",        3);

	obs_properties_add_int_slider(props, SETTING_PIXEL_SIZE,
	                              "Pixel Size", 1, 32, 1);

	return props;
}

static void cga_get_defaults(obs_data_t *settings)
{
	obs_data_set_default_int(settings, SETTING_PALETTE,    0);
	obs_data_set_default_int(settings, SETTING_PIXEL_SIZE, 1);
}

static void cga_update(void *data, obs_data_t *settings)
{
	struct cga_filter_data *filter = data;

	int mode = (int)obs_data_get_int(settings, SETTING_PALETTE);
	filter->palette_mode = (mode >= 0 && mode <= 3) ? mode : 0;

	int ps = (int)obs_data_get_int(settings, SETTING_PIXEL_SIZE);
	filter->pixel_size = (ps >= 1) ? ps : 1;
}

/* ------------------------------------------------------------------ */

static void *cga_create(obs_data_t *settings, obs_source_t *source)
{
	struct cga_filter_data *filter = bzalloc(sizeof(*filter));
	filter->context = source;

	char *effect_path = obs_module_file("shaders/cga-dither.effect");

	if (!effect_path) {
		blog(LOG_ERROR, "[cga-filter] obs_module_file returned NULL — "
		               "data directory not found");
		bfree(filter);
		return NULL;
	}

	char *errors = NULL;
	obs_enter_graphics();
	filter->effect = gs_effect_create_from_file(effect_path, &errors);
	obs_leave_graphics();

	if (!filter->effect) {
		blog(LOG_ERROR, "[cga-filter] Failed to compile '%s':\n%s",
		     effect_path, errors ? errors : "(no details)");
		bfree(errors);
		bfree(effect_path);
		bfree(filter);
		return NULL;
	}

	bfree(errors);
	bfree(effect_path);

	filter->param_resolution =
		gs_effect_get_param_by_name(filter->effect, "resolution");
	filter->param_pixel_size =
		gs_effect_get_param_by_name(filter->effect, "pixel_size");
	filter->param_pal[0] =
		gs_effect_get_param_by_name(filter->effect, "pal0");
	filter->param_pal[1] =
		gs_effect_get_param_by_name(filter->effect, "pal1");
	filter->param_pal[2] =
		gs_effect_get_param_by_name(filter->effect, "pal2");
	filter->param_pal[3] =
		gs_effect_get_param_by_name(filter->effect, "pal3");

	cga_update(filter, settings);
	return filter;
}

static void cga_destroy(void *data)
{
	struct cga_filter_data *filter = data;

	obs_enter_graphics();
	gs_effect_destroy(filter->effect);
	obs_leave_graphics();

	bfree(filter);
}

static void cga_render(void *data, gs_effect_t *effect)
{
	struct cga_filter_data *filter = data;

	obs_source_t *target = obs_filter_get_target(filter->context);
	uint32_t width  = obs_source_get_base_width(target);
	uint32_t height = obs_source_get_base_height(target);

	if (!width || !height)
		return;

	if (!obs_source_process_filter_begin(filter->context, GS_RGBA,
	                                     OBS_NO_DIRECT_RENDERING))
		return;

	// Push the four active palette colours to the shader
	int mode = filter->palette_mode;
	for (int i = 0; i < 4; i++) {
		struct vec3 c = {
			.x = palette_data[mode][i][0],
			.y = palette_data[mode][i][1],
			.z = palette_data[mode][i][2],
		};
		gs_effect_set_vec3(filter->param_pal[i], &c);
	}

	gs_effect_set_vec2(filter->param_resolution,
	                   &(struct vec2){ (float)width, (float)height });
	gs_effect_set_float(filter->param_pixel_size, (float)filter->pixel_size);

	obs_source_process_filter_end(filter->context, filter->effect, 0, 0);

	UNUSED_PARAMETER(effect);
}

/* ------------------------------------------------------------------ */

static struct obs_source_info cga_filter_info = {
	.id             = "cga_dither_filter",
	.type           = OBS_SOURCE_TYPE_FILTER,
	.output_flags   = OBS_SOURCE_VIDEO,
	.get_name       = cga_get_name,
	.create         = cga_create,
	.destroy        = cga_destroy,
	.video_render   = cga_render,
	.get_properties = cga_get_properties,
	.get_defaults   = cga_get_defaults,
	.update         = cga_update,
};

bool obs_module_load(void)
{
	obs_register_source(&cga_filter_info);
	return true;
}
