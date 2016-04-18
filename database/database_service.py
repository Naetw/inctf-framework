import json
import random
import datetime
import iso8601
import string


from flask import Flask, request, abort, render_template
app = Flask(__name__)
app.config.from_object('settings')

from flaskext.mysql import MySQL
mysql = MySQL()
mysql.init_app(app)

FLAG_POSSIBILITIES = string.ascii_uppercase + string.digits + string.ascii_lowercase
POINTS_PER_CAP = 100

DB_SECRET = "YOUKNOWSOMETHINGYOUSUCK"


@app.route("/")
def hello():
    return render_template('homescreen.html')


@app.route("/state")
def current_state():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    # first, get the current state

    current_tick, seconds_to_next_tick = get_current_tick(c)

    result = {}
    result['state_id'] = current_tick
    result['state_expire'] = seconds_to_next_tick

    c.execute("""select team_id, service_id, host_ip, host_port from services_locations;""")
    result['locations'] = c.fetchall()

    c.execute("""select id, exploit_containers_host from game limit 1""")
    record = c.fetchone()
    result['game_id'] = record['id']
    result['exploit_containers_host'] = record['exploit_containers_host']

    # need to decide what scripts to run

    c.execute("""select scripts.id as script_id, scripts.is_bundle as is_bundle,
              scripts.name as script_name, scripts.type as type, scripts.service_id
              as service_id from scripts""")

    result['scripts'] = c.fetchall()

    c.execute("""select scripts_run_status.json_list_of_scripts_to_run as json_list
              from scripts_run_status where scripts_run_status.tick_id = %s""",
              (current_tick,))

    row = c.fetchone()
    if row is not None:
        result['run_scripts'] = json.loads(row['json_list'])
    else:
        result['run_scripts'] = None

    c.execute("""select id, name, registry_namespace, image_name, team_id, service_id
              from containers where type='exploit'""")

    result['exploit_containers'] = c.fetchall()

    return json.dumps(result)


@app.route("/getgameinfo")
def get_game_info():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()
    result = {}
    c.execute("""select id as team_id, team_name from teams""")
    result['teams'] = c.fetchall()

    c.execute("""select id as service_id, name as service_name, internal_port,
              flag_id_description, description from services""")
    result['services'] = c.fetchall()

    return json.dumps(result)


@app.route("/getservicesstate")
def get_services_state():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    current_tick, _ = get_current_tick(c)

    teams = get_services_state_by_tick(current_tick, c)

    return json.dumps({"teams": teams})


@app.route("/getservicesstate/<tick_id>")
def get_services_state_tick(tick_id):
    # TODO: FIX ME
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    teams = get_services_state_by_tick(tick_id, c)

    return json.dumps({"teams": teams})


def get_services_state_by_tick(tick_id, c):

    # Get the timeframes of the tick
    c.execute("""select created_on, time_to_change from ticks where id = %s""",
              (tick_id,))
    result = c.fetchone()
    if result is not None:
        tick_start_time = result['created_on']
        tick_end_time = result['time_to_change']
    else:
        tick_start_time = 0
        tick_end_time = 0

    c.execute("""select id from teams""")
    teams = []

    for result in c.fetchall():
        team_id = result['id']
        c.execute("""select id from services""")

        services = []
        for result in c.fetchall():
            service_id = result['id']
            c.execute("""select state from team_service_state where team_id = %s and
                      service_id = %s and created_on > %s and created_on < %s""",
                      (team_id, service_id, tick_start_time, tick_end_time))
            service_status = -1
            service_statuses = []
            for result in c.fetchall():
                service_statuses.append(result['state'])

            if len(service_statuses) != 0:
                service_status = min(service_statuses)
            services.append({'service_id': service_id, 'state': service_status})

        teams.append({"team_id": team_id, "services": services})
    return teams


@app.route("/setservicestate/<teamid>/<serviceid>", methods=['GET'])
def set_state(teamid, serviceid):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    status = int(request.args.get('status'))
    reason = request.args.get('reason')
    if not (status == 2 or status == 1 or status == 0):
        abort(400)

    c = mysql.get_db().cursor()
    c.execute("""insert into team_service_state (team_id, service_id, state, reason,
              created_on) values (%s, %s, %s, %s, %s)""",
              (teamid, serviceid, status, reason,
               datetime.datetime.now().isoformat()))

    result = {"result": "great success"}
    mysql.get_db().commit()

    return json.dumps(result)


@app.route("/allscripts")
def all_scripts():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    c.execute("""select id, name, type, is_ours, is_bundle, feedback, team_id,
              service_id, is_working, latest_script from scripts""")

    result = {'scripts': c.fetchall()}
    return json.dumps(result)


@app.route("/script/<scriptid>")
def get_script(scriptid):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    c.execute("""select id, name, type, is_ours, is_bundle, feedback, team_id,
              service_id, is_working, latest_script from scripts where id = %s limit
              1""", (scriptid,))

    script = c.fetchone()

    c.execute("""select payload from script_payload where script_id = %s order by
              created_on desc limit 1""", (scriptid,))
    payload = c.fetchone()
    script.update({'payload': payload['payload']})
    return json.dumps(script)


@app.route("/ranscript/<scriptid>")
def ran_script(scriptid):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    defending_team = request.args.get('team_id')
    error = int(request.args.get('error'))
    error_msg = request.args.get('error_msg')

    c = mysql.get_db().cursor()
    c.execute("""select is_ours, type, team_id, service_id from scripts where id = %s
              limit 1""", (scriptid,))
    script = c.fetchone()

    if script['type'] == "exploit":
        abort(500)
        return

    c.execute("""insert into script_runs (script_id, defending_team_id, error,
              error_msg, created_on) values (%s, %s, %s, %s, %s)""",
              (scriptid, defending_team, error, error_msg,
               datetime.datetime.now().isoformat()))

    mysql.get_db().commit()

    return json.dumps({'result': 'great success'})


# flag stuff
@app.route("/newflag/<teamid>/<serviceid>")
def create_new_flag(teamid, serviceid):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    flag = generate_new_flag()

    c.execute("""insert into flags (team_id, service_id, flag, created_on) values
              (%s, %s, %s, %s)""", (teamid, serviceid, flag,
                                    datetime.datetime.now().isoformat()))

    result = {'flag': flag}

    mysql.get_db().commit()

    return json.dumps(result)


@app.route("/setcookieandflagid/<flag>")
def set_cookie_and_flag_id(flag):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    cookie = request.args.get('cookie')
    flag_id = request.args.get('flag_id')

    c = mysql.get_db().cursor()

    c.execute("""update flags set flag_id = %s, cookie = %s where flag = %s""",
              (flag_id, cookie, flag))

    mysql.get_db().commit()

    return json.dumps({'result': "great success"})


@app.route("/getlatestflagandcookie/<teamid>/<serviceid>")
def get_latest_flag_and_cookie(teamid, serviceid):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    c.execute("""select flag, cookie, flag_id from flags where team_id = %s and
              service_id = %s order by created_on desc limit 1""",
              (teamid, serviceid))

    return json.dumps(c.fetchone())


@app.route("/getlatestflagids")
def get_latest_flag_ids():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    flag_ids = {}

    c.execute("""select id from teams""")

    for result in c.fetchall():
        team_id = result['id']

        c.execute("""select id from services""")
        flag_ids[team_id] = {}
        for result in c.fetchall():
            service_id = result['id']

            c.execute("""select flag_id from flags where team_id = %s and service_id
                      = %s order by created_on desc limit 1""", (team_id, service_id))
            result = c.fetchone()
            if result:
                flag_id = result['flag_id']
                flag_ids[team_id][service_id] = flag_id

    to_return = {'flag_ids': flag_ids}
    return json.dumps(to_return)


@app.route("/submitflags/<team_id>")
def submit_flags(team_id):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    flags = map(str, json.loads(request.args.get('flags')))
    c = mysql.get_db().cursor()
    c.execute("""select id, team_id, service_id, flag from flags where flag in %s and
              created_on >= (select max(created_on) from ticks)""" %
              (str(tuple(flags))))
    flag_details = {}
    for row in c.fetchall():
        flag_details[row['flag']] = row

    c.execute("""select flag from flag_submission where team_id = %s and created_on
              >= (select max(created_on) from ticks)""" % (team_id))
    submitted_flags = {}
    for row in c.fetchall():
        submitted_flags[row['flag']] = True

    submission_details = {'correct': 0, 'incorrect': 0, 'self': 0, 'duplicate': 0,
                          'points': 0}
    for flag in flags:
        duplicate_flag = False
        if flag not in flag_details:
            submission_details['incorrect'] += 1
        elif flag in submitted_flags:
            submission_details['duplicate'] += 1
            duplicate_flag = True
        elif flag_details[flag]['team_id'] == team_id:
            submission_details['self'] += 1
        else:
            submission_details['correct'] += 1
            points = POINTS_PER_CAP
            submission_details['points'] += points
            message = """Captured active flag from service %s from team %s""" % \
                      (flag_details[flag]['service_id'],
                       flag_details[flag]['team_id'])
            c.execute("""insert into team_score (team_id, score, reason) values (%s, %s, %s)""",
                      (team_id, points, message))

        if not duplicate_flag:
            c.execute("""insert into flag_submission (team_id, flag) values (%s,
                      %s)""", (team_id, flag))

    mysql.get_db().commit()
    return json.dumps(submission_details)


@app.route("/submitflag/<teamid>/<flag>")
def submit_flag(teamid, flag):
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    # check if flag already submitted by this team

    c.execute("""select id from flag_submission where team_id = %s and flag = %s""",
              (teamid, flag))

    result = c.fetchone()
    if result:
        return json.dumps({'result': "alreadysubmitted", 'points': None})

    c.execute("""insert into flag_submission (team_id, flag, created_on) values (%s,
              %s, %s)""", (teamid, flag, datetime.datetime.now().isoformat()))

    c.execute("""select id, service_id, team_id from flags where flag = %s""",
              (flag,))

    to_return = {}

    result = c.fetchone()

    # valid flag
    if result:
        # check if the flag is the latest
        submitted_id = result['id']
        submitted_service = result['service_id']
        submitted_team_id = result['team_id']

        if submitted_team_id == int(teamid):
            to_return = {'result': 'ownflag', 'points': None}
        else:
            c.execute("""select id from flags where team_id = %s and service_id = %s
                      order by created_on desc limit 1""",
                      (submitted_team_id, submitted_service))
            result = c.fetchone()
            latest_flag_id = result['id']

            if latest_flag_id == submitted_id:
                # Success! Give this team some points!
                points = POINTS_PER_CAP
                message = """Submitted active flag of service %s from team %s via
                           dashboard""" % (submitted_service, submitted_team_id)
                c.execute("""insert into team_score (team_id, score, reason,
                          created_on) values (%s, %s, %s, %s)""",
                          (teamid, points, message, datetime.datetime.now().isoformat()))

                to_return = {'result': 'correct', 'points': points}

            else:
                to_return = {'result': 'notactive', 'points': None}

    else:
        to_return = {'result': 'incorrect', 'points': None}

    mysql.get_db().commit()
    return json.dumps(to_return)


@app.route("/scores")
def scores():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()

    c.execute("""select team_id, SUM(score) as score from team_score group by team_id""")

    to_return = {'scores': {}}
    for result in c.fetchall():
        team_id = result['team_id']
        team_result = {}
        team_result['raw_score'] = int(result['score'])

        sla_percentage = get_uptime_for_team(team_id, c)
        team_result['sla'] = int(sla_percentage)
        team_result['score'] = team_result['raw_score'] * (sla_percentage / 100.0)
        to_return['scores'][team_id] = team_result

    return json.dumps(to_return)


@app.route("/teams")
def team_list():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()
    c.execute("""select id as team_id, team_name, services_ports_low as port_low,
              services_ports_high as port_high from teams;""")
    teams = c.fetchall()
    return json.dumps(teams)


@app.route("/services")
def services_list():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()
    c.execute("""select id as service_id, name as service_name, internal_port as
              int_port, offset_external_port as off_ext_port from services;""")
    services = c.fetchall()
    return json.dumps(services)


@app.route("/container_changed", methods=['POST'])
def container_changed():
    secret = request.headers.get('secret')

    if secret != DB_SECRET:
        app.logger.error("Got invalid secret: %s. Aborting." % (secret))
        abort(401)

    known_container_types = ["exploit", "service"]
    callback_content = json.loads(request.get_data())
    events = callback_content['events']
    app.logger.info("Got %d events" % (len(events)))
    for event in events:
        if event['action'] != 'push':
            app.logger.info("Ignoring event %s" % (event['action']))
            continue

        namespace, image_name = event['target']['repository'].split('/')
        curr_digest = event['target']['digest']
        container_type = image_name.split('_')[0]
        if container_type not in known_container_types:
            app.logger.warn("Unknown type %s. Namespace: %s, image_name: %s" %
                            (container_type, namespace, image_name))
            continue

        app.logger.info("Namespace: %s, image_name: %s, type: %s" % (namespace,
                        image_name, container_type))
        c = mysql.get_db().cursor()

        c.execute("""select latest_digest from containers where registry_namespace =
                  %s and image_name = %s and type = %s""",
                  (namespace, image_name, container_type))
        result = c.fetchone()
        if not result:
            if container_type.lower() == "service":
                app.logger.warning("""No service container found with image name %s
                                   in namespace %s. Not processing further""" %
                                   (image_name, namespace))
                continue
            elif container_type.lower() == "exploit":
                # Exploit container was created just now. Insert into DB and continue.
                app.logger.warning("""Creating exploit container entry for %s""" %
                                   (image_name))
                team_name = namespace
                service_name = image_name.split('_')[1]
                container_name = '_'.join([image_name, team_name])
                c.execute("""SELECT id FROM teams where team_name = %s""",
                          (team_name, ))
                result = c.fetchone()
                if result is None:
                    app.logger.warning("No team with name %s found" % (team_name))
                    continue

                team_id = result["id"]
                c.execute("""SELECT id FROM services where name = %s""",
                          (service_name, ))
                result = c.fetchone()
                if result is None:
                    app.logger.warning("No service with name %s found" % (service_name))
                    continue

                service_id = result["id"]
                values = (container_name, namespace, image_name, team_id, service_id,
                          "EXPLOIT")
                c.execute("""INSERT INTO containers(name, registry_namespace,
                          image_name, team_id, service_id, type) VALUES(%s, %s, %s,
                          %s, %s, %s)""", values)
                continue

        latest_digest = result['latest_digest']

        if latest_digest == curr_digest:
            app.logger.info("No new changes detected.")
            continue

        app.logger.info("update_required set to True for image %s in namespace %s" %
                        (image_name, namespace))
        app.logger.info("Current digest is %s" % (curr_digest))

        c.execute("""update containers set update_required = True, latest_digest = %s
                  where registry_namespace = %s and image_name = %s and type = %s""",
                  (curr_digest, namespace, image_name, container_type))

    mysql.get_db().commit()
    return "OK"


@app.route("/ranexploit/")
def ran_exploit():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    attacking_team = int(request.args.get('attacker'))
    service_id = int(request.args.get('service_id'))
    stdout = request.args.get('stdout')
    stderr = request.args.get('stderr')
    correct = int(request.args.get('correct'))
    incorrect = int(request.args.get('incorrect'))
    self = int(request.args.get('self'))
    duplicate = int(request.args.get('duplicate'))
    total = int(request.args.get('total'))
    points = int(request.args.get('points'))

    c = mysql.get_db().cursor()
    c.execute("""insert into exploits_status(service_id, attacking_team_id,
              exploit_stdout, exploit_stderr, correct_count, incorrect_count,
              self_count, duplicate_count, points, target_count) values (%s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s)""", (service_id, attacking_team, stdout,
                                               stderr, correct, incorrect, self,
                                               duplicate, points, total))

    mysql.get_db().commit()

    return json.dumps({'result': 'great success'})


@app.route("/exploitlogs")
def get_exploit_logs():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()
    c.execute("""select created_on from ticks order by created_on desc limit 1""")
    result = c.fetchone()
    if result is not None:
        tick_start_time = result["created_on"]
        c.execute("""select service_id, attacking_team_id as attacker_id,
        correct_count as correct, incorrect_count as incorrect, duplicate_count as
        duplicate, self_count as self, target_count as total, exploit_stdout as
        stdout, exploit_stderr as stderr from exploits_status where created_on >
        %s""", (tick_start_time, ))

        exploit_details = c.fetchall()
    else:
        exploit_details = {}

    return json.dumps({"exploits_logs": exploit_details})


@app.route("/changed_containers")
def changed_containers():
    secret = request.args.get('secret')

    if secret != DB_SECRET:
        abort(401)

    c = mysql.get_db().cursor()
    c.execute("""select team_id, service_id, type from containers where
              update_required = True""")

    return json.dumps(c.fetchall())


@app.route("/tick_duration")
def get_tick_duration():
    _, seconds_to_next_tick = get_current_tick(mysql.get_db().cursor())
    return json.dumps(seconds_to_next_tick)


def get_uptime_for_team(team_id, c):

    c.execute("""select COUNT(id) as count, service_id from team_service_state where
              team_id = %s group by service_id""", (team_id,))

    total_counts = {}
    for result in c.fetchall():
        total_counts[result['service_id']] = result['count']

    c.execute("""select COUNT(id) as count, service_id from team_service_state where
              team_id = %s and state = 2 group by service_id""", (team_id,))

    up_counts = {}
    for result in c.fetchall():
        up_counts[result['service_id']] = result['count']

    uptimes = {}
    for service_id in total_counts.keys():
        total = total_counts[service_id]
        up = up_counts[service_id]
        uptime = ((up * 1.0) / (total * 1.0)) * 100

        uptimes[service_id] = uptime

    # now average all the uptimes

    total = 0
    for service_id in uptimes.keys():
        total += uptimes[service_id]

    return total / len(uptimes)


def generate_new_flag():
    new_flag = ''.join(random.choice(FLAG_POSSIBILITIES) for x in range(13))
    return "FLG" + new_flag


def get_current_tick(c):
    c.execute("""select id, time_to_change, created_on from ticks order by created_on
              desc limit 1""")
    result = c.fetchone()
    current_tick = 0
    seconds_left = 0
    if result:
        current_tick = result['id']
        current_time = iso8601.parse_date(datetime.datetime.now().isoformat())
        time_to_change = iso8601.parse_date(result['time_to_change'])

        seconds_left = (time_to_change - current_time).total_seconds()
        if seconds_left < 0:
            seconds_left = 0

    return current_tick, seconds_left

if __name__ == "__main__":
    app.run(host='127.0.0.1')
