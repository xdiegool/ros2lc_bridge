static std_msgs::Float32 stat_x;
static std_msgs::Float32 stat_y;
static std_msgs::Float32 stat_z;

static void convert_pos_in(pos_vel_posRef *src, std_msgs::Float32 **x,
		std_msgs::Float32 **y, std_msgs::Float32 **z)
{
	if (!*x)
		*x = &stat_x;
	if (!*y)
		*y = &stat_y;
	if (!*z)
		*z = &stat_z;

	stat_x.data = src->x;
	stat_y.data = src->y;
	stat_z.data = src->z;
}

static void convert_pos_in_free(std_msgs::Float32 **x, std_msgs::Float32 **y,
		std_msgs::Float32 **z)
{
	// Nothing to do here.
}

static pos_vel_velRef stat_dst;

static void convert_vel_out(const std_msgs::Float32 *dx,const  std_msgs::Float32 *dy,
		const std_msgs::Float32 *dz, const std_msgs::Float32 *dt,
		pos_vel_velRef **dst)
{
	*dst = &stat_dst;

	if (dx)
		stat_dst.dx = dx->data;
	if (dy)
		stat_dst.dy = dy->data;
	if (dz)
		stat_dst.dz = dz->data;
	if (dt)
		stat_dst.dt = dt->data;
}

static void convert_vel_out_free(pos_vel_velRef **dst)
{
	// Nothing to do here.
}

static bool do_trigger(const std_msgs::Float32 *dx,const  std_msgs::Float32 *dy,
		const std_msgs::Float32 *dz, const std_msgs::Float32 *dt)
{
	if (dx)
		return true;

	return false;
}

