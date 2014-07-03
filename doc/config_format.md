# Basic Configuration
The bridges are specified using a simple XML-based format. One
very simple configuration file looks as follows.

```xml
<bridge name="pingpong_bridge" port="7357">
  <imports>
    <topic name="/ping" />
  </imports>

  <exports>
    <topic name="/pong" />
  </exports>
</bridge>
```

When run through the generator it will create a bridge package named
pingpong\_bridge with a node named `main` that publishes to a topic
`ping` and subscribes to a topic `pong`. It will resolve the types of
these topics and put similar LabComm types in
`<ros\_workspace>/pingpong_bridge/lc/lc\_types.lc`. If the workspace
is not explicitly specified as a parameter to the generator the first
directory in `$ROS_PACKAGE_PATH` that is in the users home directory
will be used. If all else fails /tmp will be used. When the bridge is
started by

```bash
rosrun pingpong_bridge main.py
```

or, is C++ was generated,

```bash
rosrun pingpong_bridge main
```

it will listen for connection on port 7357.


# Advanced Features
For special cases there are a few special features.


## Custom conversions
```xml
<bridge name="ft_bridge" port="7357">
  <exports>
    <topic name="/force_torque" />
  </exports>

  <conversions>
    <conversion>
      <lc path="lc/ft.lc" />
      <py path="conv/ft_conv.py" function="convert_ft" />
      <sources>
        <topic name="/force_torque" />
      </sources>
      <destinations>
        <sample name="force" pseudotopic="/force_pt" />
        <sample name="torque" pseudotopic="/torque_pt" />
      </destinations>
    </conversion>
  </conversions>
</bridge>
```

This configuration will use the function `convert_ft` in the file
`ft_conv.py` to split the topic `/force_torque` into two different
samples defined in `lc/ft.lc`. These new samples are addressed in the
same way topics are and their names are given by the `pseudotopic`
attribute.


## Static Conversions
```xml
<bridge name="static_bridge" port="7357">
  <imports>
    <topic name="/ping" />
  </imports>

  <exports>
    <topic name="/pong" />
  </exports>

  <static-connections>
    <target addr="127.0.0.1:8080">
      <subscribe name="/pong" />
      <publish name="/ping" />
    </target>
  </static-connections>
</bridge>
```

This configuration will use the imports and exports in the same way
the first one did. In addition to this it will connect to `127.0.0.1:8080`
at launch and subscribe that client to the topic `pong` and let it
publish to `ping`, all without requiring the `subscribe` and
`publish` samples to be sent from the client.
